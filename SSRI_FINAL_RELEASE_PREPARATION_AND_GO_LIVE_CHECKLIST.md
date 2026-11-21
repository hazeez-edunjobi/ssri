# SSRI — Final Release Preparation and Go-Live Checklist

**Date:** 2026-11-21  
**Mode:** Technical review + local remediation + evidence capture  
**Commit / push / deploy / stage:** **not performed** (require separate owner approval)  
**Scientific status:** `scientific_validation_status = NOT_VALIDATED` · Phase 6 = **BLOCKED**

---

## Executive recommendation

| Gate | Verdict |
|------|---------|
| Local engineering (working tree) | **CONDITIONAL PASS** |
| GitHub CI (post-commit) | **NOT VERIFIED** (no push) |
| Live production readiness | **NOT VERIFIED** for go-live |
| **GO / NO-GO** | **NO-GO** until owner-approved commits, dual deploy, and **verified promoted Stage 2.5 (13-channel) checkpoint** on persistent storage |

Honest estimate toward a *verified* first production release: **~80%** locally; production checkpoint + post-deploy smoke remain the critical open gates.

---

## 1. Actual Git baseline

| Field | Verified value |
|-------|----------------|
| Branch | `main` |
| HEAD | `d06878699f398a3b364a3ce48498c9cc0149786d` |
| Remote tracking | `main...origin/main` |
| Divergence | **0 ahead / 0 behind** |
| Staged index | **empty** |
| Working tree | **dirty** (release work uncommitted) |

Approved baseline matches current HEAD. Commit C authentication history is preserved; no reset/rebase/amend.

---

## 2. Working-tree inventory

### Tracked modifications (vs HEAD)

| Area | Paths (summary) |
|------|-----------------|
| Assess / training / health | `model/.../assess.py`, `training.py`, `health.py`, `app.py` |
| Ruff-only | 17 additional model src/test files (see Commit 1) |
| Auth/assess fixtures | `auth_helpers.py`, assess/demo/release-shell/geotiff/location/audit tests |
| Frontend assess + hazards | `dashboard/page.tsx`, `page.tsx`, `api.ts`, shell/operator/e2e small edits |
| Excluded tracked noise | `poc/release_shell/scripts/inspect_client_csv.py` (**EXCLUDE**) |

### Untracked — include in release commits (when approved)

- `frontend/lib/assessRequest.ts`, `assessRequest.test.ts`
- `frontend/lib/productCapabilities.ts`, `productCapabilities.test.ts`
- `frontend/components/product/ProductCapabilities.tsx`
- `model/tests/test_assess_checkpoint_authorization.py`
- `model/tests/test_assess_checkpoint_resolution.py`

### Untracked — exclude

- All `poc/_tmp_*`
- `poc/release_shell/configs/abeokuta_provisional.hypotheses.json`
- Client/Abeokuta audit & prep docs (`SSRI_ABEOKUTA_*`, `SSRI_CLIENT_*`)
- Prior session reports (optional docs commit only if owner wants them)
- `.env`, credentials, raw CSVs, copied datasets

**No `git add .` / `git clean` / restore performed.** All existing work preserved.

---

## 3. Checkpoint security review

Verified against current source in `assess.py`, `training.py`, `auth/authorization.py`, and dependencies.

### Authorization matrix

| Principal | Active model assessment | Explicit checkpoint | Non-active model ID | Geological mutation |
|-----------|-------------------------|---------------------|---------------------|---------------------|
| Anonymous | **Denied** (401) | Denied | Denied | Denied |
| USER (`RUN_ASSESS`) | **Allowed** via active registry | **Denied** (403) | **Denied** (403) unless id == active | **Denied** (no `MANAGE_GEOLOGICAL`) |
| Operator (`RUN_INFERENCE` + geo) | Allowed | **Allowed** under `output_root` jail | Allowed | Allowed |
| Admin | Allowed | Allowed under jail | Allowed | Allowed |
| API key | Existing RBAC | Per key permissions | Per key permissions | Per key permissions |

### Confirmed behaviours

| Requirement | Status | Evidence |
|-------------|--------|----------|
| Ordinary users only assess active promoted model | **Pass (local)** | `resolve_assessment_checkpoint`; USER denied path / non-active id |
| Explicit checkpoint requires operator permission | **Pass (local)** | `can_override_assessment_checkpoint` → `Permission.RUN_INFERENCE` |
| Path jail under `output_root` (resolve + `relative_to`) | **Pass (local)** | `_ensure_path_under_root`; traversal rejected |
| Error messages avoid filesystem path disclosure | **Pass (local)** | Generic “outside allowed storage root” / “not found at the provided operator path” |
| Non-active `model_id` requires `RUN_INFERENCE` | **Pass (local)** | `_MODEL_ID_OVERRIDE_DENIED` |
| Active-model naming by USER equals active resolution | **Pass (local)** | `model_id == active_id` → active path |
| Assessment rate-limited | **Pass (local)** | `Depends(require_run_assess_rate_limited)` |
| Supabase auth server-verified | **Pass (local code)** | Commit C `auth/dependencies.py` (not weakened) |
| API-key RBAC backward compatible | **Pass (local code)** | Role/permission map unchanged for keys |

Regression suite: `tests/test_assess_checkpoint_authorization.py` — **18 passed**, exit 0.

---

## 4. Model selection authorization review

Resolution order in `resolve_assessment_checkpoint`:

1. Authorized operator **checkpoint** override (path jail).
2. Authorized **non-active** `model_id` (or active id treated as active).
3. **Active** promoted registry checkpoint.
4. Fail closed with actionable `_NO_PRODUCTION_CHECKPOINT_MESSAGE`.

Missing registry entry / missing file → `InvalidServiceRequestError` (fail closed).  
No production demo-checkpoint invent path for ordinary assess (demo remains server `SSRI_DEMO_MODE` only).

---

## 5. Path-disclosure findings

| Endpoint | Ordinary `READ_STATUS` | Operator (`RUN_INFERENCE`) |
|----------|------------------------|----------------------------|
| `GET /api/v1/training/models` | `_public_model_payload` — **no** `checkpoint_path` / `experiment_dir` | Full `to_dict()` |
| `GET /api/v1/training/models/active` | `checkpoint_path: null`; public active metadata + `checkpoint_available` | Path + full record |

**Finding (remediated this session):** list endpoint previously could expose internal paths via `to_dict()` to any `READ_STATUS` caller. Now consistently redacted unless `RUN_INFERENCE`.

Tests: `test_list_models_hides_paths_from_user`, `test_list_models_reveals_paths_to_operator`, plus active-endpoint equivalents.

Assess responses expose `checkpoint_sha256` / optional `checkpoint_id` (stem under release-shell), not absolute filesystem paths.

---

## 6. Assessment resolution verification

| Check | Result |
|-------|--------|
| Frontend `buildAssessRequestBody` omits empty checkpoint/model_id | **Pass** |
| Dashboard does not invent checkpoint paths | **Pass** (empty → omit; API resolves) |
| No implicit demo checkpoint in production assess path | **Pass** (server demo flag only) |
| 13-channel live contract enforced against loaded checkpoint | **Pass** (mismatch rejected; no pad/truncate/zero-fill) |
| Schema-v2 16-channel features rejected against 13-ch checkpoint | **Pass** (explicit error) |
| Ordinary user cannot bypass via client path | **Pass** (403) |
| Ordinary user cannot select historic model_id | **Pass** (403) |

**Verification class:** Implemented + verified **locally**. Not verified against live production assess (no authenticated prod smoke).

---

## 7. Hazard / geological capability verification

| Item | Result |
|------|--------|
| Hazards: Subsidence, Landslide, Sinkhole | Present in `PRODUCT_HAZARDS` + `ProductCapabilities` |
| Geological conditioning separate (overburden, lineament density/distance, ingestion) | Present in `PRODUCT_GEOLOGICAL` — not a fourth hazard |
| Live-inference-pending labels | Present on geo entries |
| `NOT_VALIDATED` / no fabricated accuracy | Safeguard copy in UI |
| `mergeHazardNames` never drops canonical three | Implemented + unit-tested |
| Phase 6 | Remains **BLOCKED** |

**Verification class:** Implemented + verified **locally** (typecheck/lint/tests/build). Live Vercel page content for this working tree: **NOT VERIFIED** (frontend not redeployed with these changes).

---

## 8. Production health-timeout investigation

### Probes (2026-11-21, this session)

| URL | Result | Notes |
|-----|--------|-------|
| `https://ssri-api.onrender.com/api/v1/health` | **200** `{"status":"ok","service":"ssri-inference"}` | Succeeded with **90s** client timeout (~80s wall for health+ready sequence) |
| `https://ssri-api.onrender.com/api/v1/ready` | **200** | `postgresql`/`redis`/`queue` **ok**; `mode=distributed` |
| `https://ssri-api.onrender.com/api/v1/training/models/active` | **401** | Expected without credentials (`require_read_status`) |
| `https://ssri-gamma.vercel.app` | **200** | Frontend reachable |

### Attribution (evidence-based)

| Hypothesis | Assessment |
|------------|------------|
| 1. Render cold starts | **Likely primary cause of prior short-timeout failures** — health is trivial; long first response then success |
| 2. Application startup hang | Unlikely once process up (health returns quickly after warm) |
| 3. Database connectivity | Ready reports **connected** when warm |
| 4. Redis connectivity | Ready reports **connected** when warm; client uses 5s socket timeouts |
| 5. Worker/queue | Queue component **reachable** on ready; readiness does **not** require Celery worker liveness |
| 6. Supabase auth dependency | Health/ready **do not** call Supabase (confirmed in `health.py` docstring + code) |
| 7. Other | Prior double infrastructure probe on ready path removed locally (not yet deployed) |

**Do not invent** a stronger diagnosis than: cold-start latency + need for ≥60–90s first probe; when warm, health/ready succeed and infra components report ok.

Local readiness improvements (working tree, undeployed):

- Single `check_infrastructure_health` call (was checked twice).
- Exception message uses `type(exc).__name__` only (less leak risk).
- Documented that ready is independent of Supabase/worker process.

---

## 9. Production checkpoint verification status

```text
PRODUCTION_CHECKPOINT_VERIFICATION = NOT_VERIFIED
```

| Check | Status |
|-------|--------|
| Persistent volume at `SSRI_API_OUTPUT_ROOT=/data/outputs` mounted on Render | **NOT VERIFIED** (no console access this session) |
| Promoted Stage 2.5 checkpoint present | **NOT VERIFIED** |
| Active registry points at that checkpoint | **NOT VERIFIED** (401 without operator session) |
| Readable by API process | **NOT VERIFIED** |
| Model config declares 13 input channels | **NOT VERIFIED** on prod |
| Survives restart/redeploy | **NOT VERIFIED** |
| Compatible with production feature stack | **NOT VERIFIED** |

**GO-LIVE BLOCKER.** Do not invent or fabricate a checkpoint. Local fixtures are not production evidence.

Infra docs/examples reference `/data/outputs`; that is configuration intent, not production proof.

---

## 10. Exact backend / frontend test results

Executed this session on the dirty working tree. **Do not treat as GitHub CI.**

### Backend (`model/`)

| Command | Exit | Result |
|---------|------|--------|
| `poetry run ruff check src tests` | **0** | All checks passed |
| `poetry run pytest tests/test_assess_checkpoint_authorization.py -q --tb=line` | **0** | **18 passed** in 45.39s |
| `poetry run pytest -q --tb=line` | **0** | **857 passed, 3 skipped** in 312.96s |

### Frontend (`frontend/`)

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | **0** | Clean |
| `npm run lint` | **0** | Clean (`--max-warnings 0`) |
| `npm test` | **0** | **46 passed**, 0 failed |
| `npm run build` | **0** | Next.js build succeeded |

### Verification classes

| Claim | Class |
|-------|-------|
| Local Ruff / pytest / FE gates | **Verified locally** |
| GitHub Actions on these changes | **Not verified** (no push) |
| Live production assess / RBAC smoke | **Not verified** |
| Production checkpoint | **Not verified** |

---

## 11. Non-overlapping commit manifests (do not stage until approved)

### Critical shared-file decision

`assess.py`, `training.py`, and `test_assess_checkpoint_resolution.py` contain **both** active-model resolution and authorization/redaction. Fragile hunk splitting is unsafe.

**Revised structure (recommended): two commits** — merge former “Commit 2 + Commit 3” into one coherent assessment/security commit.

```text
Expected order:
  1) Fix repository-wide Ruff CI violations
  2) Complete active-model assessment, hazard visibility, and checkpoint authorization
Dependency: Commit 2 does not depend on Commit 1 for runtime behaviour;
            Commit 1 unblocks CI green independently and should land first.
```

### Commit 1 — Repository-wide Ruff remediation

**Subject:** `Fix repository-wide Ruff CI violations`

| Path | Change |
|------|--------|
| `model/src/ssri_model/api/app.py` | E402: `load_dotenv` after imports |
| `model/src/ssri_model/attribution/__init__.py` | Drop unused imports |
| `model/src/ssri_model/dann/train_step.py` | Drop unused `nn` |
| `model/src/ssri_model/data/feature_engineering.py` | Drop unused `from_bounds` |
| `model/src/ssri_model/evaluation/evaluator.py` | Drop unused `cast` |
| `model/src/ssri_model/manual_training/validation.py` | Trim unused channel imports |
| `model/src/ssri_model/ml/statistics_loader.py` | Drop unused `CHANNEL_COUNT` |
| `model/src/ssri_model/release_shell/evaluate.py` | Unused import / local |
| `model/src/ssri_model/release_shell/labels_inventory.py` | `Path` import for annotation |
| `model/src/ssri_model/release_shell/routes.py` | Drop unused `Request` |
| `model/src/ssri_model/release_shell/validator.py` | Unused imports / locals |
| `model/src/ssri_model/scripts/train_foundation_multitask.py` | Unused `probe` |
| `model/src/ssri_model/training/checkpoint.py` | Drop unused `cast` |
| `model/tests/test_calibration.py` | Drop unused `pytest` |
| `model/tests/test_csv_import.py` | Unused locals |
| `model/tests/test_hazard_factors_v2.py` | Unused imports |
| `model/tests/test_release_shell_softmax_contract.py` | Unused imports |
| `model/tests/test_upload_row_cap.py` | Drop unused `os` |

**18 files. Lint-only. No auth/assess behaviour.**

### Commit 2 — Assessment resolution, capabilities, authorization, readiness clarity

**Subject:** `Complete active-model assessment and hazard visibility`

*(Includes former “Harden assessment checkpoint authorization” to avoid overlapping hunks.)*

**Backend**

| Path | Included changes |
|------|------------------|
| `model/src/ssri_model/api/routes/assess.py` | Active registry resolution; RUN_INFERENCE path/`model_id` gates; output_root jail; 13-vs-16 guard; fail-closed messaging |
| `model/src/ssri_model/api/routes/training.py` | List + active path redaction via `_public_model_payload` |
| `model/src/ssri_model/api/routes/health.py` | Single infra probe; typed exception message |
| `model/tests/test_assess_checkpoint_authorization.py` | **New** RBAC + redaction tests |
| `model/tests/test_assess_checkpoint_resolution.py` | **New** resolution / channel tests |
| `model/tests/auth_helpers.py` | Fixture helpers for role principals |
| `model/tests/test_api_assess_audit.py` | Fixture paths under output root |
| `model/tests/test_assess_geotiff_and_conditioning.py` | Same |
| `model/tests/test_assess_location_provenance.py` | Same |
| `model/tests/test_demo_mode_assess.py` | Demo/assess wording + fixtures |
| `model/tests/test_release_shell_assess.py` | Compatibility |
| `model/tests/test_release_shell_assess_route.py` | Compatibility |

**Frontend**

| Path | Included changes |
|------|------------------|
| `frontend/lib/assessRequest.ts` | Request builder (no invented paths) |
| `frontend/lib/assessRequest.test.ts` | Tests |
| `frontend/lib/productCapabilities.ts` | Three hazards + geo catalogue |
| `frontend/lib/productCapabilities.test.ts` | Tests |
| `frontend/components/product/ProductCapabilities.tsx` | UI |
| `frontend/app/dashboard/page.tsx` | Active-model assess integration |
| `frontend/app/page.tsx` | Capabilities section |
| `frontend/lib/api.ts` | Active model client typing/fields |
| `frontend/app/shell/page.tsx` | Minor related |
| `frontend/app/training/operator/page.tsx` | Minor related |
| `frontend/e2e/dashboard.spec.ts` | Selector/copy updates |

### Explicitly excluded from both commits

- `poc/_tmp_*`
- `poc/release_shell/scripts/inspect_client_csv.py`
- Abeokuta / client audit documents and datasets
- `.env` / credentials / secrets
- Optional prior `SSRI_*_REPORT.md` files (separate docs commit only if requested)

**Do not stage now.** No overlapping file ownership between Commit 1 and Commit 2 under this plan.

---

## 12. Deployment prerequisites (preparation only — no deploy)

### Services and order

1. **Postgres** — reachable; migrations already applied for platform v4 as needed.
2. **Upstash Redis (TLS `rediss://`)** — broker/queue/rate-limit.
3. **Persistent disk** — `SSRI_API_OUTPUT_ROOT=/data/outputs` with promoted `best.pt` + registry active pointer.
4. **FastAPI API (Render)** — deploy Commit 1+2 image/commit; confirm env (auth, CORS, demo **off**, live acquisition as intended).
5. **Celery worker (if distributed jobs required)** — same output root / Redis / DB assumptions.
6. **Next.js frontend (Vercel)** — `NEXT_PUBLIC_API_URL` → production API; Supabase anon URL/key only; CORS allow Vercel origin.
7. **Supabase Auth** — JWT verification secrets on API only; no service-role in browser.

### Environment checklist (names only — no secret values)

- `SSRI_AUTH_ENABLED=true` (production)
- `SSRI_API_OUTPUT_ROOT=/data/outputs`
- Database URL, Redis URL, Celery broker/backend
- Supabase URL + JWT secret / anon as designed
- CORS origins including `https://ssri-gamma.vercel.app`
- `SSRI_DEMO_MODE=false` for production assess honesty

### Deploy mutation

**Not performed.** Do not claim a deployment succeeded.

---

## 13. Production smoke-test specification (post-approval deploy)

| # | Test | Expected |
|---|------|----------|
| 1 | Frontend loads | HTTP 200; three hazards visible; geo section separate |
| 2 | `GET /api/v1/health` | 200 `{status:ok}` within warm SLA; allow ≤90s on cold start |
| 3 | `GET /api/v1/ready` | 200 `status=ready`; postgres/redis/queue ok — or **503** if deps down (do not force 200) |
| 4 | Authenticated USER `POST /api/v1/assess` (no checkpoint) | 200 assess payload **or** clear 400 if no promoted model |
| 5 | Anonymous assess | **401** |
| 6 | USER with `checkpoint` path | **403** |
| 7 | USER with non-active `model_id` | **403** |
| 8 | Operator checkpoint under output root | **200** (valid ckpt) |
| 9 | Traversal / symlink escape path | **400** (or auth error) — no escape |
| 10 | Hazard UI | Subsidence, Landslide, Sinkhole visible (desktop + mobile) |
| 11 | Geological UI | Separate; pending labels; not a fourth hazard |
| 12 | USER geological mutation | **403** |
| 13 | Active checkpoint loads | Operator `GET .../models/active` shows available; USER assess uses it |
| 14 | Checkpoint channels | Loaded config **in_channels == 13** |
| 15 | Postgres + Redis | Ready components ok |
| 16 | Worker | Distributed job completes if async required |
| 17 | Rate limiting | Excess USER assess → rate-limit response |
| 18 | Path leak | USER `GET /models` and `/models/active` have **null**/absent filesystem paths |

---

## 14. Outstanding risks

1. **Production promoted checkpoint unverified** — highest severity go-live blocker.
2. Working-tree changes **not on GitHub / not deployed** — production still runs Commit C-era API behaviour for assess/redaction until deploy.
3. Render **cold-start** can still fail naive 10–30s monitors.
4. Dashboard still exposes an optional checkpoint field; security relies on **server 403** for USER (acceptable) but UX could confuse non-operators.
5. Science remains **NOT_VALIDATED**; Phase 6 **BLOCKED** — marketing must not claim production geological truth.
6. Worker process liveness is **not** part of `/ready` — monitor separately if async jobs matter.
7. No authenticated production USER assess executed this session.

---

## 15. Final GO / NO-GO

| Dimension | Verdict |
|-----------|---------|
| Local implementation completeness | **CONDITIONAL PASS** |
| Local verification (Ruff, 857 pytest, FE gates) | **PASS** |
| Commit plan safety (non-overlapping) | **PASS** (2-commit revised plan) |
| GitHub CI on new commits | **NOT VERIFIED** |
| Live production health (warm) | **PASS** (this probe) |
| Live production checkpoint | **FAIL / NOT_VERIFIED** |
| Live production auth/assess smoke | **NOT VERIFIED** |
| Scientific validation | **NOT CLAIMED** (`NOT_VALIDATED`) |

### Recommendation

**NO-GO for first verified production release.**

Proceed only after:

1. Owner approval → stage/commit per manifests (no `git add .`).
2. Push + green CI.
3. Deploy API (+ worker if needed) then frontend.
4. Operator/console confirmation of persistent `/data/outputs` + active 13-channel checkpoint.
5. Full §13 smoke with recorded status codes.

Until then, treat hosts as **research/staging-capable**, not a verified production go-live.

---

*End of checklist. No commit, push, deploy, or staging was performed while producing this document.*
