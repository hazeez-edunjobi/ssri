# SSRI — Authentication Security & Release Readiness Report

**Date:** 2026-11-21  
**Mode:** Security review + hardening implemented locally; **no commit / push / deploy**  
**Baseline tip:** `315b5eed218ec9605fab85d47e570e6cb4f561a6`  
**Phase 6:** **BLOCKED** (unchanged)  
**Production inference contract:** 13-channel Stage 2.5; `NOT_VALIDATED` (unchanged)

---

## 1. Original root cause

Production `Run Assessment` returned `AUTHENTICATION_REQUIRED` because:

1. Dashboard `submitAssess` → `frontend/lib/api.ts` `authHeaders()` only attached `NEXT_PUBLIC_SSRI_API_KEY`.
2. Signed-in users hold a **Supabase access token**, which was never forwarded.
3. Backend `/api/v1/assess` authenticated **API keys only** via `authenticate_api_key`.

---

## 2. Verified implementation (post-hardening)

### Authentication (two mechanisms preserved)

| Mechanism | Header | Credential | Resolver |
|-----------|--------|------------|----------|
| SSRI API key | `Authorization: Bearer` | `ssri_{key_id}_{secret}` | `authenticate_api_key` |
| Supabase session | `Authorization: Bearer` | Access token (JWT shape) | `verify_supabase_access_token` → profile role |

Dispatcher: `authenticate_bearer_token` — API-key prefix `ssri_` is never treated as a JWT.

### Authorization (authn ≠ authz)

| Principal | Assessment (`RUN_ASSESS`) | Catalogue mutate (`MANAGE_GEOLOGICAL`) | Admin (`MANAGE_AUTH`) |
|-----------|---------------------------|----------------------------------------|------------------------|
| Unauthenticated | Denied | Denied | Denied |
| `Role.VIEWER` (API key) | Denied | Denied | Denied |
| `Role.USER` (Supabase `profiles.role=user`) | **Allowed** | Denied | Denied |
| `Role.OPERATOR` (API key / explicit map) | Allowed | Allowed | Denied |
| `Role.ADMIN` (Supabase `admin` / API key) | Allowed | Allowed | Allowed |

**Decision:** Ordinary signed-in users intentionally may run **live assessment** only. They are **not** granted full `OPERATOR` (no `RUN_INFERENCE` batch/training API-key powers, no geological mutation, no key admin). This uses distinct permission `RUN_ASSESS` rather than promoting every user to OPERATOR.

Platform SQL (`supabase/migrations/20260929000000_platform_v4.sql`): `profiles.role` ∈ `{user, admin}` only; admin is SQL-granted, never client-writable for privilege escalation.

### Frontend

- `authHeaders()`: explicit API key → env `NEXT_PUBLIC_SSRI_API_KEY` → Supabase `getSession().access_token`.
- No service-role / admin secrets in the bundle.
- 401 vs 403 messages distinguished in `parseError`.

### Assess route

- `assess_endpoint` depends on `require_run_assess_rate_limited` (`RUN_ASSESS`), not full `RUN_INFERENCE`.

---

## 3. Supabase JWT verification findings

### How tokens are validated

`verify_supabase_access_token` (`platform/auth.py`):

1. Rejects empty / non-JWT-shaped / `ssri_`-prefixed strings **before** any network call.
2. Calls `GET {SUPABASE_URL}/auth/v1/user` with `Authorization: Bearer <token>` and the project **anon** key.
3. Accepts only HTTP 200 with a non-empty `id`.
4. **Does not** trust client-decoded claims alone.
5. **Does not** log the access token.

Cryptographic checks (signature, expiry, project binding) are performed by **Supabase Auth** for the configured project URL. A token from another project or with a bad/expired signature fails that call (non-200 → `UNAUTHENTICATED`).

### What is / is not covered locally

| Check | Status |
|-------|--------|
| Malformed token | Local reject (`looks_like_jwt`) |
| API key vs JWT confusion | Prefix / shape separation |
| Expired / bad signature / wrong project | Via Supabase Auth HTTP verification |
| Local JWKS / explicit `aud`/`iss` parse | **Not implemented** (no PyJWT/JWKS client in deps) |
| Optional `SSRI_AUTH_JWT_SECRET` local HS256 | Gate exists in `production_gate.py` but **not wired** into assess auth |

**Limitation (documented):** verification is delegated to Supabase Auth over HTTPS, not an in-process JWKS verifier. This is the existing platform pattern and avoids inventing crypto. Future hardening: optional local JWT verify with project JWT secret / JWKS before the user call.

---

## 4. Authorization and role mapping

| Input | Auth role | Notes |
|-------|-----------|-------|
| `profiles.role=user` | `Role.USER` | Default for signed-in product users |
| `profiles.role=admin` | `Role.ADMIN` | SQL-only elevation |
| Unknown / missing role string | **Fail closed** (`AuthenticationError`) | |
| No Supabase store on live token path | **Fail closed** | Prevents silent OPERATOR grant |
| Test `platform_tokens` map | Explicit role in tuple | Includes `operator`/`viewer` for tests only |

Live path loads `profiles.role` via `supabase_store_from_env()` after token verification; missing profile is upserted as **`user`** (not operator).

---

## 5. API-key compatibility

Preserved and re-tested:

- Valid operator key: assess + inference paths.
- Invalid key → `INVALID_CREDENTIALS`.
- Disabled/expired keys → rejected (`test_auth_dependencies`).
- Viewer key → assess **403** `INSUFFICIENT_PERMISSIONS`.
- API-key RBAC independent of Supabase.

---

## 6. Geological endpoint authorization matrix

| Route | Permission | `Role.USER` | `Role.OPERATOR` / `ADMIN` |
|-------|------------|-------------|---------------------------|
| `GET /geological/datasets` | `READ_STATUS` | Allow | Allow |
| `GET /geological/datasets/{id}` | `READ_STATUS` | Allow | Allow |
| `POST /geological/coverage` | `READ_STATUS` | Allow | Allow |
| `GET .../original` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |
| `POST /geological/datasets` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |
| `POST .../upload` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |
| `POST .../declare` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |
| `POST .../validate` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |
| `POST .../activation` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |
| `POST /geological/apply/offline` | `MANAGE_GEOLOGICAL` | **Deny** | Allow |

Offline apply still requires registered `target_dataset_id`; HTTP does **not** expose `allow_direct_target_root`.

---

## 7. Exact modified / new files (auth hardening)

**Modified**

- `model/src/ssri_model/auth/models.py` — `Role.USER`, `RUN_ASSESS`, `MANAGE_GEOLOGICAL`
- `model/src/ssri_model/auth/authorization.py` — permission matrix
- `model/src/ssri_model/auth/dependencies.py` — bearer resolver, fail-closed role map
- `model/src/ssri_model/api/dependencies.py` — `require_run_assess*`, `require_manage_geological`
- `model/src/ssri_model/api/routes/assess.py` — assess uses `RUN_ASSESS`
- `model/src/ssri_model/api/routes/geological.py` — mutate/original → `MANAGE_GEOLOGICAL`
- `model/src/ssri_model/platform/auth.py` — JWT shape + verification docs
- `model/src/ssri_model/geological/service.py` — unused `Path` import removed
- `frontend/lib/api.ts` — session forwarding + 401/403 copy
- `model/tests/test_auth_authorization.py`

**New**

- `model/tests/test_assess_supabase_auth.py`
- `frontend/lib/api.auth.test.ts`

**Not for this commit:** Abeokuta docs, `poc/_tmp_*`, `inspect_client_csv.py`, execution/completion reports.

---

## 8. Test commands and results

| Suite | Command | Result |
|-------|---------|--------|
| Auth-focused ruff | `poetry run ruff check` (auth/assess/geological/platform auth paths) | **PASS** |
| Auth + API auth tests | `pytest tests/test_assess_supabase_auth.py tests/test_auth_authorization.py tests/test_api_authentication.py tests/test_api_authorization.py tests/test_auth_dependencies.py tests/test_auth_credentials.py` | **38 passed** |
| Geological | `pytest tests/test_geological_*.py` | **35 passed, 1 skipped** |
| Full backend | `pytest -q` | **828 passed, 3 skipped** |
| Frontend typecheck | `npm run typecheck` | **PASS** |
| Frontend tests | `npm test` | **34 passed** |
| Frontend lint | `npm run lint` | **PASS** |
| Frontend build | `npm run build` | **PASS** |
| Full-tree ruff `src tests` | `poetry run ruff check src tests` | **FAIL** — 33 **pre-existing** issues outside auth scope (E402 in `app.py`, unused imports elsewhere). Auth-touched files are clean; CI historically already red on unrelated debt. |

Scientific contract: no channel-count / Phase 6 / checkpoint changes in this work.

---

## 9. Remaining security limitations

1. JWT crypto delegated to Supabase Auth HTTP API (no local JWKS/`aud`/`iss` enforcement in-process).  
2. Live Supabase path requires a configured platform store; otherwise fail closed (correct, but ops must keep Supabase service role available server-side).  
3. Geological UI still shows mutate controls to all signed-in users; API returns 403 — UX polish pending.  
4. `/training/operator` and `/shell` remain unauthenticated FE surfaces (pre-existing).  
5. Full-repo Ruff still fails on unrelated files — separate cleanup commit recommended for green CI.  
6. Production authenticated smoke **not** run (no deploy authorized).  
7. `NEXT_PUBLIC_SSRI_API_KEY` remains a build-time machine-key option; treat as sensitive and prefer session auth for browsers.

---

## 10. Git state

| Item | Value |
|------|--------|
| Branch | `main` @ `315b5ee` (even with `origin/main`) |
| Commit A/B | Untouched (no amend/rewrite) |
| Auth changes | Uncommitted working tree |
| Secrets / client CSV | Not included in auth file set |

### Suggested commit (owner approval required — **not executed**)

```text
Harden Supabase assess auth with least-privilege USER role.

Forward signed-in sessions to /api/v1/assess, verify tokens via Supabase Auth,
and grant RUN_ASSESS without elevating every user to OPERATOR or geological mutation.
```

Files to stage: the modified/new auth list in §7 only.

---

## 11. Release recommendation

### **PASS WITH LIMITATIONS**

The authentication fix is **safe to commit** and subsequently deploy after owner approval, provided:

1. Only the §7 auth file set is committed (exclude temps/client docs).  
2. Both **API (Render)** and **frontend (Vercel)** are redeployed together.  
3. Post-deploy smoke: signed-in assess succeeds; anonymous assess still 401; user cannot mutate geological catalogue; operator/admin can; 13-ch / `NOT_VALIDATED` / Phase 6 blocked unchanged.  
4. Follow-up tickets: local JWT/JWKS optional hardening; hide geological mutate UI for `user`; full-tree Ruff cleanup for CI green.

**Not FAIL:** least-privilege mapping is implemented; tokens are not trusted from client claims alone; API-key RBAC preserved; regressions green.

**Not unconditional PASS:** no production authenticated verification yet; JWT validation is delegated; unrelated Ruff debt remains.

---

## Closing statement

**Secure authorization first:** signed-in users get `RUN_ASSESS` only; geological mutation requires `MANAGE_GEOLOGICAL`; API keys keep independent RBAC.  
**Regression:** 828 backend + 34 frontend tests passed; FE build/lint/typecheck passed.  
**Release:** **PASS WITH LIMITATIONS** — approve a dedicated auth commit + dual-host deploy, then run authenticated production smoke before calling the incident closed.
