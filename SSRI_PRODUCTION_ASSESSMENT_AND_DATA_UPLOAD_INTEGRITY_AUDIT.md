# SSRI — Production Assessment & Data Upload Integrity Audit

**Audit mode:** READ-ONLY (no source edits, deploys, uploads, registry changes, or credential use)  
**Audit time (UTC):** 2026-11-23  
**Local HEAD:** `d6e877a3d40e698ba9662a38ce652e51ba8a6131` (`fix: enforce production demo disablement and data integrity`)  
**Frontend:** `https://ssri-gamma.vercel.app`  
**Backend:** `https://ssri-api.onrender.com`  
**Scientific status:** `NOT_VALIDATED` (unchanged; not contradicted)

---

## A. Executive summary

| Capability | Status | One-line evidence |
|------------|--------|-------------------|
| Frontend / backend version compatibility | **PASS** | Live OpenAPI includes `demo_mode`, `/demo/scenarios`, geological `/process` & `/compatibility` matching `d6e877a`; Vercel Production last deploy SHA `d6e877a` |
| Point assessment (production) | **FAIL** | No promoted Stage 2.5 checkpoint; FE disables Run; API ready reports `checkpoint_available: false` |
| Polygon assessment (production) | **FAIL** | Same checkpoint gate as point |
| Geological uploads (code + OpenAPI) | **PARTIAL** | Full lifecycle implemented in repo and exposed in live OpenAPI; end-to-end durability on Render **NOT_VERIFIED** without credentials / persistent-disk proof |
| Other dataset uploads (training / platform) | **PARTIAL** | Routes present; live success **NOT_VERIFIED** (auth + storage) |
| Dataset processing (TMI grid, etc.) | **PARTIAL** | Implemented + OpenAPI present; production run **NOT_VERIFIED** |
| Dataset retrieval | **PARTIAL** | Authenticated original download route exists; live retrieve **NOT_VERIFIED** |
| Dataset activation | **PARTIAL** | Implemented with validation gates; live activate **NOT_VERIFIED** |
| Storage durability (geological / checkpoints) | **FAIL** (risk) / **NOT_VERIFIED** (disk) | Code requires durable `SSRI_API_OUTPUT_ROOT`; Render Free local FS is ephemeral unless persistent disk proven |
| Checkpoint persistence | **FAIL** (availability) | Live registry: no active model / checkpoint unavailable |
| Gravity overlay | **FAIL** (overlay only) | Live `GET /layers/gravity` → **404**; explicitly **not** required for assess |

**Primary assessment blocker:** missing promoted Stage 2.5 checkpoint in the training registry on the API host — not a frontend bug and not the gravity overlay.

---

## B. Production deployment verification

### B.1 Local repository

| Item | Value |
|------|-------|
| Branch | `main` tracking `origin/main` |
| HEAD | `d6e877a3d40e698ba9662a38ce652e51ba8a6131` |
| Working tree | Clean of integrity commit; untracked audit/tmp markdown and `poc/_tmp_*` only |

### B.2 Live frontend

| Evidence | Result |
|----------|--------|
| GitHub Deployments (Vercel) | Latest Production: SHA **`d6e877a`**, `vercel[bot]`, 2026-11-21T23:30:19Z |
| Alias | `https://ssri-gamma.vercel.app` |
| `/about` | **200**; copy includes “Live hazard scores require…”; **no** “Sample result” |
| `/dashboard` | **200** (auth-gated client app) |
| `NEXT_PUBLIC` default API | `frontend/lib/env.ts` → `https://ssri-api.onrender.com` when production build omits override |

### B.3 Live backend

| Endpoint | HTTP | Safe excerpt / keys |
|----------|------|---------------------|
| `GET /api/v1/health` | **200** | `{"status":"ok","service":"ssri-inference"}` |
| `GET /api/v1/ready` | **200** | `status=ready`; infra postgres/redis/queue **ok**; **`demo_mode`: false**; **`model_registry`**: `active_model_id=null`, `checkpoint_available=false`, detail *“No promoted Stage 2.5 model is configured…”* |
| `GET /openapi.json` | **200** | **67** paths; includes `/api/v1/assess`, `/demo/scenarios`, full geological set including `/process` & `/compatibility`, training, platform, layers/gravity |
| `GET /api/v1/demo/scenarios` | (in OpenAPI) | Present in contract; gated when demo off |
| `GET /api/v1/training/models/active` | **401** | `AUTHENTICATION_REQUIRED` (expected unauthenticated) |
| `POST /api/v1/assess` (no auth) | **401** | No hazard scores returned |
| `GET /api/v1/layers/gravity` | **404** | Overlay GeoTIFF missing; message states visualization-only |

### B.4 Deployed backend vs expected source

| Question | Finding |
|----------|---------|
| Matches `d6e877a` contract? | **PASS (contract-level)** — prior audit (2026-11-21) saw ready **without** `demo_mode`/`model_registry`; live ready **now** exposes both. OpenAPI now lists geological process/compatibility and demo routes. |
| Exact container image SHA? | **NOT_VERIFIED** — no Render deploy receipt in GitHub Deployments API (only Vercel entries) |
| Frontend/backend SHA skew? | **PASS** for integrity remediation SHA on FE; BE behavior consistent with same commit family |

### B.5 Checks blocked without credentials

- Authenticated `GET /training/models/active` body  
- Authenticated `POST /assess` missing-checkpoint error body  
- Geological create/upload/validate/process/activate  
- Platform dataset version upload  
- Training zip ingest  
- Workspace counts  
- Whether `SSRI_API_OUTPUT_ROOT` is on a Render persistent disk  

---

## C. Assessment root causes

### C.1 Call chain (source)

1. **UI** `frontend/app/dashboard/page.tsx` — map AOI (point/polygon), `loadActiveModelStatus()`, `onAssess` → `submitAssess`.  
2. **Preflight** `GET /api/v1/training/models/active` via `frontend/lib/api.ts` → `activeModelFromResponse` (`frontend/lib/activeModelStatus.ts` 53–76).  
3. **Disable** `assessmentButtonDisabled` / `hasAssessmentModelAccess` (113–141): requires `kind === "available"` and `checkpointAvailable`, unless operator checkpoint override or gated presentation demo.  
4. **User-visible copy** `modelStatusPanelMessage` missing branch (158): *“No promoted Stage 2.5 checkpoint is configured…”* — matches live ready detail.  
5. **API** `POST /api/v1/assess` → `resolve_assessment_checkpoint` (`model/.../api/routes/assess.py` 183–265) → raises `_NO_PRODUCTION_CHECKPOINT_MESSAGE` (54–57) when no active registry checkpoint file.  
6. **Registry** `{SSRI_API_OUTPUT_ROOT}/training/models/active.json` + `registry.json` + `{model_id}/best.pt` (`manual_training/registry.py`).  
7. **Readiness mirror** `active_model_registry_status` (`api/registry_status.py` 17–28) — live response confirms no promoted model.  
8. **Execution model** Assess is **synchronous HTTP** (not Celery). Async exists for `/inference/async` / training jobs only.  
9. **Channel contract** `CHANNEL_NAMES` / `CHANNEL_COUNT=13` (`ml/constants.py` 22–38); live path rejects feature/checkpoint channel mismatch (`assess.py` 460–468).  
10. **Demo** Production clamp + live `demo_mode:false` — not substituting catalogue scores.

### C.2 Root cause classification

| Hypothesis | Verdict |
|------------|---------|
| Frontend preflight falsely blocking | **No** — aligned with live registry |
| Authentication alone | **Contributes to UX** (401 without session) but **not** the “no checkpoint” message root once signed in |
| Missing model registry / active pointer | **Yes — P1** |
| Missing / unavailable checkpoint file | **Yes — P1** (ready: `checkpoint_available: false`) |
| Ephemeral storage of prior promotions | **Plausible P0 risk** if promotions ever existed on ephemeral disk — **NOT_VERIFIED** historically |
| Model architecture incompatibility | **N/A** until a checkpoint exists |
| Request validation | Secondary once checkpoint exists |
| API deployment mismatch | **Resolved vs prior audit** at contract level |
| Gravity overlay | **Not** an assess dependency (`layers.py` 147–150; live 404) |

### C.3 Separate conditions (honest split)

| Condition | Live / code status |
|-----------|-------------------|
| API process health | **PASS** |
| Infrastructure ready (PG/Redis/queue) | **PASS** |
| Checkpoint availability | **FAIL** |
| Model loadability | **NOT_VERIFIED** (nothing to load) |
| Model compatibility (13-ch Stage 2.5) | **NOT_VERIFIED** |
| Scientific validation | **NOT_VALIDATED** |
| Production inference availability | **FAIL** |

**Do not bypass** the missing-checkpoint gate to “make assess work.”

---

## D. Upload workflow matrix

Legend: **I** = implemented in source · **O** = present in live OpenAPI · **V** = verified end-to-end in production this audit · **D** = durable binary storage proven

### D.1 Geological catalogue (`/api/v1/geological/*`)

| Stage | Status | Evidence |
|-------|--------|----------|
| FE selection / upload UI | I | `frontend/app/geological/page.tsx`, `[id]/page.tsx` |
| Auth (`manage_geological` mutate) | I / O | Routes require manage; list/get read_status |
| Create dataset | I / O | `POST /datasets` |
| Upload CSV/ZIPCSV/lineament | I / O | `POST …/upload`; ZIPCSV single-CSV + path-traversal rejection (`geological/service.py`) |
| Declare metadata / column map / CRS | I / O | `POST …/declare` |
| Validate | I / O | `POST …/validate` (TMI irregular cloud path in `tmi.py`) |
| Process (TMI grid) | I / O | `POST …/process` |
| Compatibility decision | I / O | `POST …/compatibility` |
| Catalogue registration / provenance | I | `GeologicalStorage` under `{output_root}/geological/` |
| Async job | **Missing** | Synchronous API only — no `JobType` for geological |
| Retrieval (original) | I / O | `GET …/original` |
| Activation | I / O | `POST …/activation` (TMI cannot be approved into Stage 2.5 stack) |
| Offline apply to training dataset | I / O | `POST /apply/offline` — **not** live assess channel injection |
| Survives Render redeploy | **NOT_VERIFIED** | Requires durable disk |

### D.2 Manual training (`/api/v1/training/*`)

| Stage | I | O | V | Notes |
|-------|---|---|---|-------|
| Dataset create / zip upload / register-path / validate | ✓ | ✓ | NOT_VERIFIED | Zip path traversal + size limits (`upload_limits.py`) |
| Training job | ✓ | ✓ | NOT_VERIFIED | Celery `JobType.TRAINING` |
| Model list / activate / deactivate / active | ✓ | ✓ | NOT_VERIFIED | Activation is the assess gate |
| Schema | Stage 2.5 zip: `feature_stack.npy` (13,H,W) + labels — **not** raw X/Y/Z TMI as training package | | | |

### D.3 Platform v4 (`/api/v1/platform/*`)

| Stage | I | O | V | Notes |
|-------|---|---|---|-------|
| Dataset / version zip | ✓ | ✓ | NOT_VERIFIED | Optional Supabase Storage `datasets` bucket (`platform/supabase_store.py` 177–181) + FS extract |
| Training runs | ✓ | ✓ | NOT_VERIFIED | Uses Stage 2.5 trainer; completion stays `NOT_VALIDATED` |
| Model promote | ✓ | ✓ | NOT_VERIFIED | Must not promote synthetic |

### D.4 Release shell (`/api/v1/release-shell/*`)

| Stage | Notes |
|-------|-------|
| Present in OpenAPI | Operator/lab path; gated by `SSRI_RELEASE_SHELL` |
| Production ordinary users | Not the customer assess path |

---

## E. Storage and persistence matrix

| Artifact | Metadata location | Binary storage | Durable by design? | Survives Render redeploy? |
|----------|-------------------|----------------|--------------------|---------------------------|
| Geological datasets | `{output_root}/geological/**/dataset.json`, `index.jsonl` | `{output_root}/geological/.../original|working` | Only if `output_root` on persistent volume (`durable.py` 1–22, 50–62) | **NOT_VERIFIED** on live Render |
| Training datasets | TrainingStorage under `{output_root}/training/` | Same FS tree | Same | **NOT_VERIFIED** |
| Platform dataset zips | Supabase Postgres tables | Supabase Storage bucket `datasets` **when** service-role configured; else/also FS | Supabase objects: durable if configured | **NOT_VERIFIED** (prod config unknown) |
| Raster/GeoTIFF assess outputs | Assessment JSON under `{output_root}/assessments/` | Optional ObjectStorage (local/S3/R2) via `put_bytes` | Depends on `SSRI_OBJECT_STORAGE_BACKEND` | **NOT_VERIFIED** |
| Model checkpoints | `registry.json` / `active.json` | `{output_root}/training/models/{id}/best.pt` | Requires durable `output_root` | **FAIL availability now**; durability **NOT_VERIFIED** |
| Model registry | FS JSON under training models | FS | Same | Same |
| Assessment outputs | FS assessments dir | FS + optional object store | Same | **NOT_VERIFIED** |

**Critical design fact:** Geological catalogue **refuses** incomplete R2/S3-only backends (`durable.py` 53–62). Production must use filesystem + durable mount — not “Supabase Storage alone” for geological.

---

## F. Frontend/backend contract mismatches

| Area | Match? | Notes |
|------|--------|-------|
| Assess request (`point` / `polygon_geojson` / optional `checkpoint` / `model_id`) | **Match** | `assessRequest.ts` omits empty checkpoint |
| Active model preflight | **Match** | FE uses `checkpoint_available`; ready exposes same concept anonymously |
| Geological multipart field `file` | **Match** | Documented in FE upload client |
| Demo activation in production FE | **Match** | `productionIntegrity.ts` + live `demo_mode:false` |
| Marketing sample scores | **Match** | Removed on live `/about` |
| Gravity optional | **Match** | FE tolerates 404; API states non-blocking |
| Authenticated assess error vs FE button | **Aligned** | Both enforce missing checkpoint |

No material route/method mismatch found for the ordinary assess + geological paths between `d6e877a` source and live OpenAPI.

---

## G. Findings by severity

### P0-001 — Ephemeral filesystem risk for catalogues and checkpoints
- **Severity:** P0  
- **Status:** OPEN (architectural)  
- **Where:** `model/src/ssri_model/geological/durable.py` 1–22, 50–62; `manual_training/registry.py` / `TrainingStorage` under `SSRI_API_OUTPUT_ROOT`  
- **Evidence:** Code documents Render/ephemeral unsafety; geological refuses partial object backends. Live host durability **NOT_VERIFIED**.  
- **Impact:** Uploads and promotions can vanish after redeploy → assess remains broken / data loss.  
- **Root cause:** FS catalogue design without proven persistent disk.  
- **Remediation:** Confirm/attach Render persistent disk shared by API+worker at `SSRI_API_OUTPUT_ROOT`; or complete object-storage catalogue (not partial).

### P1-001 — No promoted Stage 2.5 checkpoint (assess blocked)
- **Severity:** P1  
- **Status:** CONFIRMED LIVE  
- **Where:** `api/registry_status.py` 22–28; `assess.py` 54–57, 248–265; `activeModelStatus.ts` 157–158, 113–121  
- **Evidence:** Live ready `model_registry.checkpoint_available=false`; FE copy matches.  
- **Impact:** Point and polygon Run assessment disabled; inference unavailable.  
- **Root cause:** Empty/missing active registry promotion on API storage.  
- **Remediation:** Promote a genuine non-synthetic Stage 2.5 checkpoint onto durable storage (owner-authorized); do not use demo/handover/synthetic.

### P1-002 — Live AOI acquisition may still fail after promote
- **Severity:** P1 (conditional)  
- **Status:** NOT_VERIFIED live flags  
- **Where:** `api/acquisition.py` (`SSRI_LIVE_ACQUISITION_ENABLED`); `assess.py` feature resolve  
- **Evidence:** Source requires live acquisition or offline `.npy` for AOI assess.  
- **Impact:** Even with a checkpoint, map clicks may fail without GEE/DEM/geophysics.  
- **Remediation:** Verify production env flags/credentials after checkpoint exists.

### P2-001 — Gravity overlay missing
- **Severity:** P2  
- **Status:** CONFIRMED LIVE  
- **Where:** `api/routes/layers.py` 137–152  
- **Evidence:** Live **404** with visualization-only disclaimer.  
- **Impact:** Map overlay unavailable; **does not** block assess.  
- **Remediation:** Mount `GRAVITY_DATA_PATH` or serve from durable object storage.

### P2-002 — Geological processing is synchronous / no worker job type
- **Severity:** P2  
- **Status:** CONFIRMED CODE  
- **Where:** `jobs/models.py` JobType enum; geological routes  
- **Evidence:** No geological Celery type; TMI process runs in request.  
- **Impact:** Large grids may time out on free-tier HTTP limits.  
- **Remediation:** Keep sync for small surveys; queue large process jobs later if needed.

### P3-001 — Presentation demo strings remain in FE bundles
- **Severity:** P3  
- **Status:** KNOWN  
- **Where:** Gated modules under `presentationDemo.ts`  
- **Evidence:** Prior bundle scan; activation blocked by `NODE_ENV=production`.  
- **Impact:** None for production activation; code size only.

---

## H. Tests and verification

### H.1 Live production probes (this audit)

| Check | Result |
|-------|--------|
| health / ready / openapi | **PASS** (see §B) |
| demo_mode false | **PASS** |
| model_registry empty | **PASS** (confirms assess blocker) |
| assess unauth | **401** (no mock scores) |
| gravity | **404** |
| FE sample card absent | **PASS** |
| Authed E2E assess / upload | **NOT RUN** (no credentials) |

### H.2 Local safe tests run

```text
cd model
poetry run pytest tests/test_demo_mode_assess.py::test_demo_mode_false_uses_real_path_and_requires_checkpoint tests/test_registry_status.py tests/test_geological_upload_durability.py -q --tb=line
```

| Result | **11 passed** (exit 0) |
|--------|------------------------|

These are **unit/local** tests — not production E2E proof.

### H.3 Not run

- Full pytest suite  
- Frontend Playwright / e2e against production  
- Any test writing to production DB/storage/queue  
- Authenticated production upload or assess  

---

## I. Recommended remediation plan

### 1. Deployment / version alignment
- **Done (contract):** FE `d6e877a` + live API ready/OpenAPI aligned with integrity commit.  
- **Acceptance:** Ready continues to expose `demo_mode` + `model_registry`; OpenAPI stays in sync after future deploys.

### 2. Assessment availability
- **Action:** On durable storage, promote a real Stage 2.5 (13-ch) checkpoint via training activate/promote flows.  
- **Dependencies:** P0 durable disk; non-synthetic training package (still a scientific gate).  
- **Acceptance:** `ready.model_registry.checkpoint_available=true`; FE Run enabled; authed assess returns real inference or clear acquisition errors — **not** demo scores. Keep `NOT_VALIDATED`.

### 3. Durable storage
- **Action:** Prove/configure Render persistent disk for `SSRI_API_OUTPUT_ROOT` shared by API+worker; document path.  
- **Acceptance:** Registry + geological files survive redeploy (owner-verified).

### 4. Upload / validation integrity
- **Action:** After disk proof, run operator-auth geological CSV→validate→(optional process) on staging/prod.  
- **Acceptance:** Catalogue entry + original bytes retrievable; failed validation blocks activation.

### 5. Async processing
- **Action:** Monitor TMI process timeouts; add job type only if measured need.  
- **Acceptance:** No silent success without derived artifact.

### 6. Frontend reliability
- **Action:** Keep missing-checkpoint messaging; ensure signed-in users see ready registry detail.  
- **Acceptance:** No fabricated scores; gravity 404 remains non-blocking.

### 7. Observability
- **Action:** Log registry active id / checkpoint present (no absolute paths to clients); alert when `checkpoint_available` false in production.  
- **Acceptance:** Operators see ready.model_registry without filesystem leakage.

---

## J. Explicitly preserved safeguards

This audit did **not**:

- Modify repository source, config, tests, or migrations  
- Commit, push, merge, or deploy  
- Change environment variables, DB rows, registry, or storage  
- Upload datasets to production  
- Activate, promote, or register a checkpoint  
- Enable demo mode or bypass auth/readiness gates  
- Fabricate predictions or substitute mock inference  
- Change or claim scientific validation other than **`NOT_VALIDATED`**  
- Expose secrets, tokens, or private paths  

---

## Bottom line

Production frontend and backend are **contract-compatible** with `d6e877a`. Map assessments cannot run because **no promoted Stage 2.5 checkpoint is configured** on the API (confirmed by live `/api/v1/ready` and FE preflight). Geological and training **upload APIs exist and match the repo**, but **production durability and authenticated E2E success are NOT_VERIFIED**; filesystem catalogues remain **unsafe on ephemeral Render disk** until persistent storage is proven. Gravity overlay is **down** and **optional**. Scientific status remains **`NOT_VALIDATED`**.
