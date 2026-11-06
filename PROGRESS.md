# PROGRESS — finish/frontend-align-rc3 (FRONTEND ALIGNMENT, LOCAL ONLY)

**Branch:** `finish/frontend-align-rc3` from local `main`
**Remote:** do not push · **Identity:** hazeez-edunjobi \<ifeoluwasuccess520@gmail.com\> · no Co-authored-by
**Flag:** `SSRI_RELEASE_SHELL` stays default OFF; behaviour with the flag off is unchanged.

## Step 0 — state re-establishment (this session)
- No rebase / merge / cherry-pick in progress.
- 22 commits ahead of `main`; author AND committer on all are `hazeez-edunjobi` (SHAs in older reports are stale — history was rewritten locally).
- One uncommitted file at resume: `frontend/lib/api.ts` (mid-Task-2 plain-language error context). Committed as `WIP Task 2` (no work discarded).
- Baseline re-run GREEN: frontend `typecheck` / `lint` / `build` pass; backend release-shell subset `28 passed`.

## Task status on this branch
- Task 1 ALIGNMENT AUDIT — DONE (commit `28471f9`, `ALIGNMENT_TABLE.md`).
  - 3 real hazards (subsidence/landslide/sinkhole); `liquefaction` invented class removed (M1–M3).
  - Dashboard/operator/shell hazard lists derive from the backend registry (`settings.hazards`); status endpoint exposes registry + channel schemas (M4/M5/M6/M7).
  - `AssessResultModal` colour map no longer keyed by hazard name (M8); `parseError` plain-language (M9); `lib/report.ts` HTML export added (M10).
- Lint / typecheck / build — DONE (commit `085791f` "Make frontend lint pass under ESLint 9 flat config").
- `frontend/lib/report.ts` report builder + reworked `AssessResultModal` — DONE (Task 1).
- Task 2 UPLOAD FLOW CHECK — DONE.
  - Plain-language context threaded through **every** API call in `frontend/lib/api.ts` (0 bare `parseError(response)` left); `parseError`/`extractErrorMessage` unwrap FastAPI `detail[]`, shell `{error:{code,message}}` and `no_trained_model`; never surfaces a stack trace or `[object Object]`.
  - UI field names/types confirmed against the backend request models (dataset JSON, multipart `file`/`layer_name`/`crs`/`working_crs`, `/jobs` body `dataset_id/epochs/seeds/device`).
  - New API contract tests `model/tests/test_release_shell_upload_contract.py` (**23 tests**) covering every upload type success + failure: ZIP (ok, non-zip, wrong suffix, oversize→413, malformed manifest), point-grid CSV headed/headerless/tab/comma/space, CRS required/invalid, working-CRS reprojection, label inventory CSV+GeoJSON (ok, no CRS, unknown hazard), lineament GeoJSON (ok, bad JSON), schema-mismatch validation FAIL, `/jobs` type contract, and flag-OFF refusal.
  - Backend hardening found by the tests: a malformed manifest with a non-list `channels` (or non-dict `channel_schema`) raised an unhandled `TypeError` → **500**; now degrades to a reportable validation result (`channel_schema.schema_from_manifest`, `manual_training/validation.py`).

---

# PROGRESS — feature/hazard-factors-v2 (LOCAL ONLY)

**Branch:** `feature/hazard-factors-v2` from local `main`  
**Remote:** do not push  
**Identity:** hazeez-edunjobi \<ifeoluwasuccess520@gmail.com\> · no Co-authored-by

## Done
- Task 1: CLIENT_CSV_FINDINGS.md (Abeokuta CSV inspected from copy)
- Task 2: point_grid_csv.py (headerless/headed, CRS required, streaming, gaps)
- Task 3: channel_schema.py v1/v2; assess mismatch messaging
- Task 4: labels_inventory.py + hazards registry
- Task 5: configurable block size (km/deg) + local evidence string
- Task 6: preview_unevaluated_scores (default OFF)
- Task 7: 10 additive tests; suite 142 OFF/ON; verify pass; frozen MATCH; rehearsal
- Task 8: DATASET_SPEC / README_OWNER / OWNER_API_GUIDE / LIMITATIONS updated
- HAZARD_FACTORS_V2_REPORT.md written
- pyproj 3.7.2 added to model poetry deps

## Blocked
- (none)

## Assumptions
- Local main already contained staging merge (release shell present)
- Abeokuta CRS/units/meaning remain UNKNOWN until client answers
- Full multi-seed v2 ZIP train deferred; FEATURE_LAYER_ONLY path verified for client CSV format

---

# MASTER TASK — finish/SSRI platform RC2 (LOCAL ONLY, no push)

**Working branch:** `feature/hazard-factors-v2` · **Identity:** hazeez-edunjobi \<ifeoluwasuccess520@gmail.com\>

## Task status
- Task 1 CLOSE OPEN VERIFICATIONS — DONE (commit 21c873f)
  - 1a tip line unpinned → "see git rev-parse HEAD"
  - 1b `validate_point_grid_layer` surfaces UNIT_SANITY WARN; Abeokuta negative-Z demo VERIFIED (overall=WARN, min −212.76, 11250 negatives); tests added
  - 1c per-seed e2e table + aggregate gate from SYNTHETIC v2 log VERIFIED
- Task 2 /shell UI COVERAGE — DONE (commit b2e324d) [4h time box]
  - Backend routes added: layers/validate, labels/inventory, lineaments/inspect; status now returns `settings`
  - Frontend /shell "Prepare owner inputs" panel: CRS per layer, layer name/channel mapping, label inventory, lineaments, settings (block size, schema versions, preview toggle)
  - See FINISH_REPORT.md UI coverage table; OWNER_API_GUIDE.md retained as fallback
- Task 3 HOST READINESS — DONE
  - Lockfile: pyproj in main deps (`^3.6.1`); DeepSlide optional group `optional=true` (segmentation-models-pytorch, h5py). `poetry install --with deepslide --dry-run --no-root` EXIT=0, pyproj 3.7.2 resolves.
  - Docker build uses `--only main` so DeepSlide is intentionally excluded from the image (not needed for release-shell/assess). Build risk: proxy body limit is above our 1 GiB handler; torch pinned 2.5.1 CPU in image vs 2.13.0 in dev.
  - Upload/memory guidance added to `poc/release_shell/UPLOAD_CAP_REPORT.md` (measured SYNTHETIC profile, 442,368 cells / 9 blocks).
  - `poc/release_shell/scripts/smoke_staging.py` written (urllib-only; production guard VERIFIED, exit 2).
  - Sandbox limitation: full fresh-venv `poetry install` blocked; dry-run + fresh pip venv (h5py/smp/torch import OK) used as evidence.
- Task 4 RUNBOOK + TOOLING — DONE
  - `poc/release_shell/RUNBOOK_FIRST_REAL_RUN.md`; `poc/release_shell/scripts/check_site_readiness.py` (tested OK).
  - Abeokuta ESTIMATE (56 km site): 5 km ≈132 blocks, 10 km ≈42, 20 km ≈12; default 50 km buffer infeasible here.
- Task 5 HUMAN-DEPENDENT DOCS — DONE (`poc/release_shell/handoff/`: CLIENT_QUESTIONS.md, OWNER_STATUS.md, REVIEW_REQUEST.md, REMAINING_WORK_REGISTER.md)
- Task 6 FINAL VERIFICATION — DONE (tip 8819c81)
  - Full suite OFF: 703 passed, 2 skipped (331.34s); ON: 703 passed, 2 skipped (241.07s)
  - Curated 151 passed (was 143; +8 tests this branch)
  - verify.py `{"pass": true}`; frozen hashes all MATCH; diff vs main frozen/checkpoints EMPTY
  - Skips named: test_readiness_with_real_services, test_postgres_job_lifecycle
  - Identity: authors all hazeez-edunjobi; 0 Co-authored-by; committer mismatch on 4 newest commits (REPORTED)
- FINISH_REPORT.md — DONE
- Bug fix (Task 4 finding): `block_id` truncation collapsed km blocks into integer degrees — fixed + regression test (commit e4875ca).
