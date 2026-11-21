# SSRI — Authentication Hardening Commit Manifest

**Mode:** READ-ONLY commit preparation (no stage / commit / push / deploy)  
**Date:** 2026-11-21  
**Verdict:** **PASS WITH LIMITATIONS**  
**Security report:** `SSRI_AUTHENTICATION_SECURITY_AND_RELEASE_READINESS_REPORT.md`

---

## 1. Current branch and HEAD

| Item | Value |
|------|--------|
| Branch | `main` |
| HEAD | `315b5eed218ec9605fab85d47e570e6cb4f561a6` |
| Upstream | `main...origin/main` (even) |
| Index | **empty** (`git diff --cached` empty) |
| Working tree | Auth hardening unstaged + unrelated leftovers |

---

## 2. Relationship to existing geological commits

| Commit | Hash | Status |
|--------|------|--------|
| Commit A (geological implementation) | `e65929fe5b35ed8dd3b14f3b029ef2091cb0d8d7` | **Present, untouched** (ancestor of HEAD) |
| Commit B (documentation) | `315b5eed218ec9605fab85d47e570e6cb4f561a6` | **HEAD, untouched** |
| Proposed Commit C (auth hardening) | — | **Not created** — this manifest only |

No amend, reset, rebase, squash, or rewrite of A/B occurred or is proposed.

The proposed commit would sit **on top of** `315b5ee` as a third, separate commit.

---

## 3. Exact proposed file list (matches report §7)

**12 files** — implementation + directly associated tests only.

### Modified (10)

| Path | Role |
|------|------|
| `model/src/ssri_model/auth/models.py` | `Role.USER`, `RUN_ASSESS`, `MANAGE_GEOLOGICAL` |
| `model/src/ssri_model/auth/authorization.py` | Least-privilege permission matrix |
| `model/src/ssri_model/auth/dependencies.py` | Bearer resolver; fail-closed role map |
| `model/src/ssri_model/api/dependencies.py` | `require_run_assess*`, `require_manage_geological` |
| `model/src/ssri_model/api/routes/assess.py` | Assess → `require_run_assess_rate_limited` |
| `model/src/ssri_model/api/routes/geological.py` | Mutations/original → `MANAGE_GEOLOGICAL`; drop unused `Form` |
| `model/src/ssri_model/platform/auth.py` | JWT shape gate; Supabase `/auth/v1/user` verify |
| `model/src/ssri_model/geological/service.py` | Remove unused `Path` import (Ruff cleanup tied to auth commit) |
| `frontend/lib/api.ts` | Session forwarding via `authHeaders()`; 401/403 copy |
| `model/tests/test_auth_authorization.py` | USER / permission matrix tests |

### New (2)

| Path | Role |
|------|------|
| `model/tests/test_assess_supabase_auth.py` | Assess + geological authz + JWT verification tests |
| `frontend/lib/api.auth.test.ts` | 401/403 messaging tests |

### Optional (owner decision — **not** in report §7 core list)

| Path | Recommendation |
|------|----------------|
| `SSRI_AUTHENTICATION_SECURITY_AND_RELEASE_READINESS_REPORT.md` | Optional docs companion |
| `SSRI_AUTHENTICATION_COMMIT_MANIFEST.md` | This file — optional process artifact |

Default recommendation: **exclude** optional docs from Commit C unless the owner wants the security pack in the same commit.

---

## 4. Change summary

| Scope | Approx. delta (tracked proposed files) |
|-------|------------------------------------------|
| File count | **12** (10 modified + 2 untracked new) |
| `git diff --numstat` (10 modified) | ~274 insertions / ~64 deletions (auth paths; CRLF warnings only) |
| Mixed auth+unrelated in one file? | **No** among the 12 proposed files |
| Unrelated dirty file | `poc/release_shell/scripts/inspect_client_csv.py` — **exclude** (preserve locally) |

Diff inspection vs report §7: **aligned**. No discrepancy requiring stop.

---

## 5. Staged versus unstaged state

| State | Content |
|-------|---------|
| Staged | **Nothing** |
| Unstaged (auth) | The 10 modified paths above |
| Untracked (auth) | `test_assess_supabase_auth.py`, `api.auth.test.ts` |
| Unstaged (exclude) | `poc/release_shell/scripts/inspect_client_csv.py` |
| Untracked (exclude) | Abeokuta/client docs, completion/execution reports, `poc/_tmp_*`, `poc/release_shell/configs/abeokuta_provisional.hypotheses.json` |

---

## 6. Test results (re-verified this session)

| Check | Command | Result |
|-------|---------|--------|
| Auth-path Ruff | `poetry run ruff check` (auth/assess/geological/platform auth + related tests) | **PASS** (`RUFF=0`) |
| Auth + geological | `pytest` auth suites + `test_geological_*.py` | **73 passed, 1 skipped** |
| Full backend | `poetry run pytest -q --tb=line` | **828 passed, 3 skipped** (`FULL=0`) |
| Frontend typecheck | `npm run typecheck` | **PASS** |
| Frontend lint | `npm run lint` | **PASS** |
| Frontend tests | `npm test` | **34 passed** |
| Frontend build | `npm run build` | **PASS** |
| Full-tree Ruff `src tests` | (known from prior review) | **Pre-existing failures** outside auth scope — not introduced by this commit set |

---

## 7. Security review summary (reconfirmed)

| Requirement | Status |
|-------------|--------|
| Supabase tokens verified server-side | **Yes** — `GET {SUPABASE_URL}/auth/v1/user` with project anon key |
| Fail closed on verify failure | **Yes** — non-200 / missing `id` → auth error |
| Network timeout bounded | **Yes** — `timeout=15.0` |
| Outage cannot authenticate | **Yes** — HTTP errors → 503/`AuthenticationError`; no principal issued |
| Malformed / `ssri_` tokens off JWT path | **Yes** — `looks_like_jwt` |
| Access tokens never logged | **Yes** — no token in logs/errors (audit uses `key_id` only) |
| `Role.USER` ≠ OPERATOR/ADMIN | **Yes** — only `READ_*` + `RUN_ASSESS` |
| `RUN_ASSESS` ≠ geological mutate | **Yes** — mutations need `MANAGE_GEOLOGICAL` |
| API-key RBAC intact | **Yes** — `ssri_` prefix still uses key store |
| Assess rate limiting | **Yes** — `require_run_assess_rate_limited` |
| Production auth bypass | **No** — when `SSRI_AUTH_ENABLED`, credentials required |
| Disabled/deleted users | **Partial** — invalid/expired sessions rejected by Supabase Auth; no separate SSRI ban-list beyond Auth |

---

## 8. Explicit excluded-file confirmation

**Must NOT stage/commit with Commit C:**

- `poc/release_shell/scripts/inspect_client_csv.py` (unrelated dirty POC)
- Abeokuta raw CSV / working COPY
- `.env` / credentials
- `SSRI_ABEOKUTA_PROVISIONAL_INTEGRATION_PREP.md`
- `SSRI_CLIENT_LINEAMENT_OVERBURDEN_DATA_AUDIT.md`
- `poc/release_shell/configs/abeokuta_provisional.hypotheses.json`
- `poc/_tmp_*` probe/debug artifacts
- Geological implementation already in Commit A
- Unrelated completion docs (`SSRI_GEOLOGICAL_RELEASE_EXECUTION_REPORT.md`, `SSRI_MASTER_COMPLETION_ASSESSMENT_AND_100_PERCENT_ROADMAP.md`) unless owner explicitly expands scope

---

## 9. Proposed commit message

```
Harden Supabase assessment authentication and permissions
```

Longer body (optional):

```
Forward signed-in Supabase sessions to assess, verify tokens via Supabase Auth,
and grant RUN_ASSESS without elevating every user to OPERATOR or geological mutation.
```

---

## 10. Remaining limitations

1. JWT cryptography delegated to Supabase Auth HTTP API (no local JWKS/`aud`/`iss` in-process).  
2. Geological UI may still show mutate controls to `user` roles; API correctly returns 403.  
3. Full-tree Ruff still red on unrelated pre-existing issues (CI hygiene follow-up).  
4. No production authenticated smoke until owner-approved deploy of **both** API and frontend.  
5. Phase 6 remains **BLOCKED**; 13-channel / `NOT_VALIDATED` unchanged.

---

## Execution status

| Action | Status |
|--------|--------|
| Manifest created | **Yes** (this file) |
| Stage | **Not performed** |
| Commit | **Not performed** |
| Push | **Not performed** |
| Deploy | **Not performed** |

**Stop.** Await owner approval before staging or committing anything.
