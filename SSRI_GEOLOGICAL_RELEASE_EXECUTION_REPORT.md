# SSRI — Geological Release Execution Report

**Date:** 2026-11-21  
**Branch:** `main`  
**Approved baseline:** `28908383555136d63dc7d15283472850e1a456c8`  
**Remote tip verified:** `315b5eed218ec9605fab85d47e570e6cb4f561a6` (`origin/main` and `https://github.com/hazeez-edunjobi/ssri` `refs/heads/main`)  
**Phase 6:** **BLOCKED** (unchanged; no 16-channel production activation)

---

## Executive verdict

Two approved commits were created on `main` and are present on `origin/main`. Local geological and frontend regression checks passed. Production hosts respond with the geological API/UI surface and a healthy distributed readiness payload. GitHub Actions **CI model job failed** on Ruff unused-import (`F401`) for Commit A files. No Vercel/Render CLI or deploy IDs were available in this environment; deployment is confirmed only by **public feature-surface smoke**, not by a logged provider deploy identifier. Authenticated catalogue/apply body behaviour was **not** exercised with production credentials.

---

## 1. Baseline and divergence

| Check | Result |
|-------|--------|
| Approved baseline still ancestor of HEAD | **Yes** — `2890838` is ancestor of `315b5ee` |
| Commit A parent | `2890838` |
| Commit B parent | `e65929f` (Commit A) |
| Local `main` vs `origin/main` | Even (`## main...origin/main`) |
| Working tree after commits | Expected leftovers only (see Exclusions) |

---

## 2. Commit A — Geological implementation

| Field | Value |
|-------|--------|
| Hash | `e65929fe5b35ed8dd3b14f3b029ef2091cb0d8d7` |
| Short | `e65929f` |
| Subject | Add geological catalogue API, UI, and offline schema-v2 apply. |

### Exact file list (28 paths)

```
frontend/app/geological/[id]/page.tsx
frontend/app/geological/page.tsx
frontend/components/platform/PlatformShell.tsx
frontend/lib/geologicalApi.ts
model/src/ssri_model/api/app.py
model/src/ssri_model/api/routes/geological.py
model/src/ssri_model/geological/__init__.py
model/src/ssri_model/geological/apply.py
model/src/ssri_model/geological/coverage.py
model/src/ssri_model/geological/inspect.py
model/src/ssri_model/geological/ledger_lock.py
model/src/ssri_model/geological/lineament_ingest.py
model/src/ssri_model/geological/models.py
model/src/ssri_model/geological/service.py
model/src/ssri_model/geological/storage.py
model/src/ssri_model/geological/target.py
model/src/ssri_model/geological/validate.py
model/src/ssri_model/release_shell/validator.py
model/tests/fixtures/geological/depth_candidate.csv
model/tests/fixtures/geological/gapped.csv
model/tests/fixtures/geological/irregular.csv
model/tests/fixtures/geological/lineaments.geojson
model/tests/fixtures/geological/negative_thickness.csv
model/tests/fixtures/geological/nonstandard_headers.csv
model/tests/fixtures/geological/regular.csv
model/tests/test_geological_acceptance_hardening.py
model/tests/test_geological_ingest.py
model/tests/test_geological_remediation.py
```

Manifest alignment: matches approved Commit A geological implementation set.  
**Intentionally omitted from Commit A (per owner approval):** `poc/release_shell/scripts/inspect_client_csv.py`.

---

## 3. Commit B — Documentation

| Field | Value |
|-------|--------|
| Hash | `315b5eed218ec9605fab85d47e570e6cb4f561a6` |
| Short | `315b5ee` |
| Subject | Document geological catalogue gates and completion baseline. |

### Exact file list (14 paths)

```
SSRI_FINAL_PROJECT_COMPLETION_REPORT.md
SSRI_GEOLOGICAL_ACCEPTANCE_HARDENING_REPORT.md
SSRI_GEOLOGICAL_CSV_INGESTION_ARCHITECTURE.md
SSRI_GEOLOGICAL_FINAL_RELEASE_GATE_REPORT.md
SSRI_GEOLOGICAL_FINAL_VERIFICATION_REPORT.md
SSRI_GEOLOGICAL_INDEPENDENT_AUDIT_REPORT.md
SSRI_GEOLOGICAL_PHASES_2_6_ACCEPTANCE_REPORT.md
SSRI_GEOLOGICAL_REMEDIATION_REPORT.md
SSRI_LIVE_V2_CONDITIONING_INTEGRATION_PLAN.md
SSRI_MASTER_COMPLETION_BASELINE.md
SSRI_MODEL_SCIENTIFIC_VALIDATION_REPORT.md
SSRI_PRE_RELEASE_COMMIT_MANIFEST.md
SSRI_PRODUCTION_SECURITY_AND_RELIABILITY_REPORT.md
SSRI_SCIENTIFIC_DATA_READINESS_REPORT.md
```

---

## 4. Excluded files confirmation

Still **not** in either commit / remain local only:

| Item | Post-release status |
|------|---------------------|
| `poc/release_shell/scripts/inspect_client_csv.py` | Modified, unstaged (`git status` shows `M`) |
| Raw Abeokuta CSV | Not committed (gitignored; not in commit trees) |
| Abeokuta working COPY | Not committed |
| `.env` / credentials | Not committed |
| Client-specific docs (`SSRI_ABEOKUTA_PROVISIONAL_INTEGRATION_PREP.md`, `SSRI_CLIENT_LINEAMENT_OVERBURDEN_DATA_AUDIT.md`) | Untracked |
| `poc/release_shell/configs/abeokuta_provisional.hypotheses.json` | Untracked under `poc/release_shell/configs/` |
| Temporary/debug (`poc/_tmp_*`, probe HTML/OpenAPI dumps) | Untracked |

No secrets were staged in Commit A or B.

---

## 5. Local regression checks (this execution)

| Check | Command | Result |
|-------|---------|--------|
| Geological backend | `poetry run pytest tests/test_geological_ingest.py tests/test_geological_remediation.py tests/test_geological_acceptance_hardening.py -q` | **PASS** — `35 passed, 1 skipped` |
| Frontend typecheck | `npm run typecheck` | **PASS** — exit 0 |
| Frontend unit tests | `npm test` | **PASS** — `31` pass / `0` fail |
| Local Ruff (geological paths) | `poetry run ruff check …geological…` | **FAIL** — 2× `F401` unused imports (`Form`, `Path`) |

### GitHub Actions (post-push)

| Run | SHA | Conclusion | Notes |
|-----|-----|------------|-------|
| [44838126525](https://github.com/hazeez-edunjobi/ssri/actions/runs/44838126525) | `315b5ee` | **failure** | `frontend` success; `model` failure on **Ruff**; `docker` skipped |
| Prior baseline CI `2890838` | also historically **failure** | Pre-existing red CI pattern on `main` |

**Recovery recommendation:** open a follow-up commit (outside the approved two-commit pack) removing unused `fastapi.Form` and `pathlib.Path` imports so CI model job can go green. Do not force-push or rewrite A/B.

---

## 6. Push confirmation

| Check | Evidence |
|-------|----------|
| `git ls-remote origin refs/heads/main` | `315b5eed218ec9605fab85d47e570e6cb4f561a6` |
| GitHub API `commits/main` | Same SHA; parent of tip is Commit A `e65929f` |
| Force-push | **Not used** |
| History rewrite / reset | **Not performed** |

Initial interactive `git push` appeared hung; non-interactive credential-less probe failed with prompt disabled; remote HEAD later matched local tip (push completed via credential manager / completed background push). Final remote verification uses `ls-remote` + GitHub API above.

---

## 7. Deployment

| Component | URL | Deploy method used here | Deploy ID |
|-----------|-----|-------------------------|-----------|
| Frontend | `https://ssri-gamma.vercel.app` | Existing Git-connected host; **no** `vercel` CLI in PATH; no local `.vercel` project link | **Not available** |
| API | `https://ssri-api.onrender.com` | Existing Git-connected host; **no** `render` CLI / deploy-hook invocation in this session | **Not available** |
| Worker | (no public URL) | Inferred via API readiness queue component | **Not available** |

**Honest deploy claim:** No provider deploy command returned a deployment identifier in this session. Production smoke (below) shows geological routes and `/geological` UI are live on the known hosts after the push. That is **feature-surface confirmation**, not a stamped deploy receipt.

---

## 8. Production smoke tests

Executed against live hosts on 2026-11-21 (UTC evening) via `curl` / Python `urllib`.

| # | Requirement | Result | Evidence |
|---|-------------|--------|----------|
| 1 | Frontend loads | **PASS** | `GET /` → 200; `Server: Vercel` |
| 2 | `/geological` loads | **PASS** | `GET /geological` → 200; HTML/JS contains `geological` |
| 3 | API health | **PASS** | `GET /api/v1/health` → 200 `{"status":"ok","service":"ssri-inference"}`; `GET /health` → 200 |
| 4 | API readiness | **PASS** | `GET /api/v1/ready` → 200; mode `distributed`; postgresql/redis/queue all `ok` |
| 5 | Authentication gate | **PASS** (unauthenticated) | `POST /api/v1/assess` → 401 `AUTHENTICATION_REQUIRED`; geological list/apply/coverage → 401 |
| 6 | Geological routes mounted | **PASS** | OpenAPI paths include `/api/v1/geological/datasets`, `…/apply/offline`, coverage, upload, validate, activation, etc. (9 geological paths) |
| 7 | Catalogue accessible to authorised users | **NOT VERIFIED** | No production auth credential used; only 401 gate confirmed |
| 8 | Offline apply requires registered `target_dataset_id` | **PARTIAL** | Source + OpenAPI: `ApplyBody` requires resolve via `target_dataset_id`; live unauthenticated calls stop at 401 before body validation |
| 9 | HTTP does not expose `allow_direct_target_root` | **PASS** | OpenAPI blob: flag **absent**; `ApplyBody` properties = `geo_ids`, `target_dataset_id`, `target_dataset_root`, `window_m` only |
| 10 | Production inference remains 13-channel contract | **PASS** (contract surface) | `release-shell/status`: `default_channel_schema=v1`, `channel_count=13`; shell disabled |
| 11 | Subsidence / landslide / sinkhole supported | **PASS** | Status hazards class_ids 0/1/2; OpenAPI text contains all three names |
| 12 | Distributed jobs / worker healthy | **PASS** (infra) | Ready components: redis connected, queue reachable. No authenticated job submission performed. `GET /api/v1/jobs` → 404 (list route not public that way) |
| 13 | Geological catalogue activation does not silently affect live assess | **PASS** (design + surface) | Apply route description: offline Stage 2.5 dataset only; assess still auth-gated; release shell disabled; default schema remains v1/13 |

CORS: `OPTIONS` assess from `https://ssri-gamma.vercel.app` → allow-origin exact match.

Scientific status advertised publicly: `NOT_VALIDATED`; release shell `enabled=false`.

---

## 9. Remaining limitations

1. **CI red on Ruff F401** in Commit A geological files — needs a small follow-up fix commit.  
2. **No provider deploy IDs** — cannot cryptographically prove container image SHA equals `315b5ee`; inference is feature-surface only.  
3. **No authenticated production smoke** — catalogue CRUD, apply-with-missing-id error code, assess response channel list, and worker job completion were not exercised with real keys.  
4. **Phase 6 remains BLOCKED** — no evaluated 16-channel checkpoint; do not activate v2 for live assess.  
5. **Client Abeokuta geology** remains out of tree (correct); scientific use still blocked pending CRS/units/validation work.  
6. Platform remains **research-ready, scientifically unvalidated, not production-qualified** for geological truth claims.

---

## 10. Phase 6 confirmation

**Phase 6 is BLOCKED.**

This release does **not**:

- activate a 16-channel checkpoint for live assessment  
- change the production default channel count away from 13  
- claim scientific validation  
- represent geological catalogue measurements as influencing live `/api/v1/assess` scores  

---

## 11. Failure / stop notes

| Step | Outcome |
|------|---------|
| Commits A & B | Succeeded |
| Push | Succeeded (remote HEAD = `315b5ee`) |
| Local geological/FE regression | Succeeded |
| GitHub CI (model/Ruff) | **Failed** — recorded; history not rewritten |
| Explicit cloud deploy CLI | **Not executed** (tools unavailable) |
| Production smoke | Hosts healthy; geological surface present; auth-gated paths not fully exercised |

No force-push, reset, or history rewrite was performed. No partial “scientific validation” claim is made.
