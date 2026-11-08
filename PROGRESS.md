# PROGRESS — finish/frontend-align-rc3 (FRONTEND ALIGNMENT, LOCAL ONLY)

**Branch:** `finish/frontend-align-rc3` from local `main`
**Remote:** do not push · **Identity:** hazeez-edunjobi \<ifeoluwasuccess520@gmail.com\> · no Co-authored-by
**Flag:** `SSRI_RELEASE_SHELL` stays default OFF; behaviour with the flag off is unchanged.

## Step 0 — state re-establishment (this session)
- No rebase / merge / cherry-pick in progress.
- 22 commits ahead of `main`; author AND committer on all are `hazeez-edunjobi` (SHAs in older reports are stale — history was rewritten locally).
- One uncommitted file at resume: `frontend/lib/api.ts` (mid-Task-2 plain-language error context). Committed as `WIP Task 2` (no work discarded).
- Baseline re-run GREEN: frontend `typecheck` / `lint` / `build` pass; backend release-shell subset `28 passed`.

## Recovery — unexpected working-tree revert, repaired (this session, LOCAL ONLY)
- **Finding (VERIFIED):** on resume the working tree was *damaged/stale*, not carrying last-session WIP. `git diff` showed `validator.py` −171 and `.gitignore` −17 that were **semantic** reverts, not line endings (`--ignore-space-at-eol --stat` gave the identical result).
  - worktree `.gitignore` was **byte-identical to `main`** (`git diff main -- .gitignore` empty); HEAD legitimately adds 17 ignore lines.
  - worktree `validator.py` was 428 lines (an intermediate pre-v2 state); **HEAD is 579 lines and correct** — it contains the v2 code (`OVERBURDEN_THICKNESS`, `schema_from_manifest`, `validate_point_grid_layer` / `unit_sanity`, `labels_present`).
  - **Mechanism: UNKNOWN.** `git stash list` empty; `git reflog` shows no checkout/restore/stash-pop touching these files; no rebase/merge/cherry-pick in progress. Attribution: external revert (harness/tool), not a recorded git operation.
- **Safety copy (VERIFIED):** full pre-recovery diff at `poc/release_shell/outputs/recovery/working_tree_before_recovery.patch`, modified files copied to `poc/release_shell/outputs/recovery/files/` (now git-ignored). Nothing discarded.
- **Action:** restored only `validator.py` and `.gitignore` from HEAD (`git checkout HEAD -- …`). Confirmed the pre-recovery patch held **no genuine new additions** in those two files (only reverts).
- **Genuine new WIP preserved as its own labelled commits:** `6c6f7dd` dashboard assess handler (`page.tsx`), `a230a34` rehearsal Playwright spec + `test:rehearsal` script, `6881ad3` ignore the recovery folder.
- **Post-recovery verification (VERIFIED):** backend release-shell + hazard-v2 subset **85 passed**; frontend `typecheck` / `lint` / **17 tests** / `build` all GREEN. Counts unchanged vs baseline → no regression from the repair.

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
- Task 3 MAP & COORDINATE CHECK — DONE.
  - **Backend (never guess a projection in the browser):** new `release_shell/geography.py` converts map clicks (always WGS84 from maplibre Web Mercator) into a checkpoint's declared CRS with pyproj `Transformer.from_crs(..., always_xy=True)`; geographic CRS returns lon/lat as-is with `axis_order="x=longitude, y=latitude"`, projected returns `x=easting, y=northing`. `parse_crs` raises a plain-language `ValueError`. `describe_checkpoint_geography` reports `crs`, `crs_declared`, `training_region`, `region_extent`, the converted point, and `inside/outside_training_region`.
  - **New read-only route** `POST /api/v1/release-shell/geography` (`routes.py`): 403 when flag OFF, 400 `INVALID_CHECKPOINT_PATH` (path traversal), 404 `CHECKPOINT_NOT_FOUND`, 422 for bad point types, `extra="forbid"` body. Hidden from flag-off clients.
  - **CRS is now persisted** into checkpoint shell meta from the dataset manifest (`shell_finalize.py` → `build_shell_meta` emits `"crs"`), so the frontend can label the checkpoint honestly.
  - **Frontend** `lib/coordinates.ts` is the single tested source of truth: `COORD_DECIMALS=6`, latitude-first `parseLatLon` with plain-language range errors, `formatLatLon` (6 dp), `isWithinCoverage`, and `pointInRegion` mirroring the backend `point_in_training_region` `pad_deg=0.5`.
  - **Dashboard** (`app/dashboard/page.tsx`): map clicks and typed coordinates round-trip to **6 decimals**; the training region is drawn as a dashed outline from `region_extent`; a geography panel shows the declared CRS + region extent + backend-converted point; an out-of-region warning matches the backend `outside_training_region` gate; assessment is **blocked with a clear message** when the checkpoint declares no CRS.
  - Tests: backend `tests/test_release_shell_geography.py` (**16**) — geographic identity, quadrant round trips 6 dp (Abeokuta 7.16/3.35, Cape Town, New York, Alice Springs), UTM 31N projected convert + round trip, invalid-CRS message, region inside/outside, no-CRS, flag-OFF 403, endpoint 404/400/422; frontend `lib/coordinates.test.ts` (**9**); Playwright e2e additions (quadrant round trip, 6-dp map click, geography panel + region warning).
  - Lint fix: restructured the geography/projected-point effects to be **keyed by checkpoint/point** (no synchronous `setState` in an effect), clearing `react-hooks/set-state-in-effect` and `exhaustive-deps`.
  - Green: frontend `typecheck`/`lint`/`build`/`test` pass; backend Task-3 subset **46 passed** (flag ON) incl. the flag-OFF 403 guard.
- Task 4 ASSESSMENT & REPORT — DONE.
  - Assessed every required path (all through the real `/api/v1/assess` route, flag ON): point **inside** the training region, point **outside** (`outside_training_region`), **no checkpoint** (`no_trained_model`), **schema mismatch** (v2 features vs v1 checkpoint → plain-language rejection, no stack trace), and each hazard state (`evaluated` → score returned; `trained, no demonstrated skill beyond slope` → score withheld; `not_available`/disabled → score withheld).
  - **Evaluation summary carried by the API**: `release_shell/evaluate.py` gains `find_evaluation_report` / `summarize_evaluation_for_report` / `load_evaluation_summary`; the assess route attaches a trimmed `evaluation_summary` (AUC + 95% CI, ΔAUC vs slope + CI, per-block table, per-seed AUC, seeds, split policy) plus `checkpoint_id`, and new notes `assess_crs`, `block_size_deg`, `local_evidence_only`. Flag OFF leaves the response unchanged (all new fields default `None`).
  - **Report** (`frontend/lib/report.ts`) now renders: lat/lon (6 dp) + training CRS + location in training CRS; checkpoint id + sha256; dataset version + hash; schema version + ordered channels; block size/buffer + local-evidence statement; per-hazard status with scores **only where the gate allows**; the evaluation summary (AUC/CI, Δ vs slope, per-block table, seeds); limitations; NOT_VALIDATED; timestamp. Wording is always "relative susceptibility ranking" — never risk, probability, detection or validation.
  - **Downloadable HTML export** reuses `buildAssessmentReportHtml`; the modal shows a progress state while running (longer assessments), then the export button.
  - Tests: backend route/report tests added (`test_release_shell_assess_route.py` +4: no-checkpoint, schema mismatch, evaluation summary + checkpoint id, summary-absent) → **15 passed** in that file, **63 passed** in the release-shell/assess subset, **20 passed** API-assess subset; frontend `lib/report.test.ts` (**8 tests**) asserts the HTML echoes API values exactly and never uses forbidden wording → **17 frontend tests** pass. `typecheck` / `lint` / `build` green.
- Task 5 SYNTHETIC REHEARSAL — DONE (this session).
  - First run **FAILED**: the dashboard blocked the assessment with "This checkpoint does not declare a CRS, so the point cannot be placed on the map." Diagnosed (VERIFIED) from the Playwright trace: **no** `POST /api/v1/assess` was ever sent; the last calls were `POST /release-shell/geography` and `GET /layers/gravity`, i.e. `onAssess` early-returned at the `crs_declared` guard.
  - **Root cause (VERIFIED):** `_run_release_shell_multiseed_training` (`api/job_workers.py`) called `finalize_checkpoint` on **only the primary seed**, so the other seeds' `best.pt` carried no `release_shell` meta. The shell UI lets the owner promote **any** seed → promoting a non-primary seed produced `crs_declared=false` and the dashboard correctly refused. Confirmed on disk: only primary-seed `best.pt` had embedded meta.
  - **Fix — commit `6ef6871`:** embed the run-level meta into **every** seed's checkpoint via `embed_in_checkpoint`.
  - **Spec hardened — commit `01d48d0`:** shared wording guard, a v1-shaped 13-channel tile for the schema-mismatch 400, and a dialog-close step before the out-of-region step.
  - **Report wording guard — commit `c7afa7a`** (`lib/report.ts` `findAffirmativeRiskClaims` + tests); **dialog Escape/focus return — commit `0e885ef`**.
  - Backend subset after the fix: **92 passed**, 657 deselected (`release_shell` + `hazard_factors_v2` + `manual_training`).
  - **Re-run after the fix (VERIFIED): `2 passed (3.5m)`**, both replay paths green:
    - owner flow (1.8m): open shell → upload+validate SYNTHETIC v2 ZIP → 3-seed train → evaluate → promote → dashboard map click (6 dp round trip) → in-region assess → download HTML report → close dialog → out-of-region warn + withhold;
    - assess error contracts (771 ms): no-checkpoint → 200 `no_trained_model` + NOT_VALIDATED; v2 checkpoint + 13-channel input → **400** `"Input features do not match the checkpoint channel schema (version v2, 16 channels). Missing channels: overburden_thickness, lineament_density, lineament_distance."` (no traceback).
  - **Timings (VERIFIED):** open 2928 ms · upload+validate 11225 ms · start job 2510 ms · wait evaluation 63604 ms · promote 1661 ms · dashboard map 2855 ms · map click 318 ms · **assess 13965 ms** · download 670 ms · close 102 ms · out-of-region 1665 ms. **Assess 14.0 s exceeds the 10 s target — recorded as an open item** (synthetic 3-seed CPU run; `mc_samples:20` + feature build).
  - Fix confirmed on disk: all three seed model dirs carry `release_shell_meta.json`.
  - Evidence committed under `poc/release_shell/outputs/frontend_rehearsal/` (7 screenshots + `assess-response.json` + `assess-error-contracts.json` + `playwright-report.json` + `rehearsal-timings.json` + `ssri-assessment-report.html`); raw `playwright-artifacts/` and `work/` ignored.

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
