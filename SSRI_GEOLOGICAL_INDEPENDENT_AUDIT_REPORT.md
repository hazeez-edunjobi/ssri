# SSRI — Independent Geological Implementation Audit Report

**Mode:** READ-ONLY verification  
**Date:** 2026-11-20  
**Auditor scope:** Claims in `SSRI_GEOLOGICAL_PHASES_2_6_ACCEPTANCE_REPORT.md` vs source, APIs, tests, and production isolation  
**Baseline HEAD:** `28908383555136d63dc7d15283472850e1a456c8` (`main`, even with `origin/main`)  
**Only file created by this audit:** this report  

---

## Executive verdict

**VERIFIED WITH GAPS**

Phases 1–5 exist as a single geological catalogue (not a duplicate system), reuse the documented shell geospatial utilities, keep live AOI acquisition off the geological path, and match the independently re-run test counts. Phase 6 is correctly **BLOCKED**.

Material gaps remain: AOI “coverage” is **bounding-box intersection only** (not valid-cell coverage); declared CSV column overrides are **not applied** during validate; offline apply accepts an **unscoped filesystem `target_dataset_root`**; catalogue has **no per-user ownership**; and some Phase 2/4 completeness items are partial (history UI, lineament duplicate detection, fiona-dependent formats).

No **CRITICAL** production isolation defect was confirmed: geological routes do not feed `acquire_feature_array_for_bbox` / live 13-channel acquisition, and `inference/safety.py` still hard-requires `CHANNEL_COUNT` (13).

---

## Repository state

| Item | Initial (audit start) | Final (audit end) |
|------|------------------------|-------------------|
| Root | `C:/Users/LENOVO/Documents/MrBusoye/ssri` | Same |
| Branch | `main` | `main` |
| HEAD | `2890838…` | `2890838…` |
| Ahead/behind `origin/main` | `0 0` | Unchanged |
| Acceptance report | **Untracked** (uncommitted) | Still untracked |
| Implementation | Uncommitted modified + untracked geological/FE files | Preserved |
| Staging | Nothing staged | Nothing staged |
| Push/deploy/reset/amend | Not performed | Not performed |

**Diff vs HEAD (implementation under audit, not introduced by auditor):**  
Modified: `frontend/components/platform/PlatformShell.tsx`, `model/src/ssri_model/api/app.py`, `poc/release_shell/scripts/inspect_client_csv.py`  
Untracked: `model/src/ssri_model/geological/**`, `api/routes/geological.py`, FE geological pages/API client, tests/fixtures, planning docs, this audit report.

Auditor authorization limited creation to this single report file. No application/test/source edits.

---

## Phase-by-phase verification

### Phase 1 — Geological CSV catalogue

| | |
|--|--|
| **Claimed** | COMPLETE |
| **Verified** | **COMPLETE (with gaps)** |

**Evidence**

- Package present: `models.py`, `storage.py`, `inspect.py`, `validate.py`, `coverage.py`, `lineament_ingest.py`, `apply.py`, `service.py`.
- Router: `model/src/ssri_model/api/routes/geological.py`; mounted in `api/app.py`.
- IDs: `geo_` + `uuid4().hex[:12]`; layout `{output_root}/geological/datasets/{geo_id}/original|working`.
- Immutability: second upload → `ORIGINAL_IMMUTABLE` (tested).
- Inspect runs without CRS; validate fails closed without CRS/measurement (tested).
- Depth vs thickness: canonicalize + apply reject depth→thickness (tested).
- Reuses `validate_point_grid_layer` / `ingest_point_grid_csv` (no second CSV engine).

**Gaps / risks**

- Declared `x_column`/`y_column`/`z_column` are **discarded** in `validate.py` (`_ = (x_column, …)`); validate always uses default column resolution in the shell validator. **MEDIUM**.
- No file locking for concurrent first-upload races. **INFO**.
- No per-dataset ownership field / ACL. **MEDIUM** (security).
- Duplicate *filenames* across different `geo_id`s are allowed (by design); collision handled via new IDs, not filename uniqueness.

**Recommended action:** Wire declared columns into working CSV rewrite or into `ingest_point_grid_csv` kwargs before validate; add owner principal id when multi-tenant auth is on.

---

### Phase 2 — Geological management UI

| | |
|--|--|
| **Claimed** | COMPLETE |
| **Verified** | **COMPLETE (with gaps)** |

**Evidence**

- Pages: `frontend/app/geological/page.tsx`, `[id]/page.tsx`.
- Central client: `frontend/lib/geologicalApi.ts` (pages call helpers; no Axios/direct `fetch` in page bodies).
- Nav: `PlatformShell` link `/geological`.
- Flows wired to real routes: list, create+upload, declare, validate, activation, coverage probe.
- Measurement select preserves `overburden_thickness` vs `depth_to_bedrock` (no silent alias in UI).
- Loading/empty/error/success states present; activation requires warning ack when WARNs exist (backend-enforced).

**Gaps**

- Upload **history** from `index.jsonl` is not exposed in UI (catalogue list only). Architecture asked for history review. **MEDIUM** completeness.
- Coverage AOI CRS input **defaults** to `EPSG:32631`; detail form uses same as placeholder. Not a production assess hardcode, but soft CRS bias. **LOW/MEDIUM**.
- No dedicated frontend unit tests for geological pages (platform `lib/**/*.test.ts` only). **LOW**.
- Offline apply API not exposed in UI (acceptable for Phase 5 API-first). **INFO**.

**Recommended action:** Surface event log; leave CRS empty by default until operator enters it.

---

### Phase 3 — AOI coverage and reporting

| | |
|--|--|
| **Claimed** | COMPLETE |
| **Verified** | **COMPLETE as bbox reporting; NOT valid-cell coverage** |

**What the endpoint actually calculates** (`coverage.py` / `POST /coverage`):

1. **AOI bbox ∩ dataset `coverage_bbox`** (axis-aligned).  
2. Fraction = intersection_area / AOI_bbox_area → labels `full` (≥0.95) / `partial` / `none`.  
3. Filters: measurement_type, validated, activated.  
4. Conflicts: ≥2 eligible matches with same measurement_type → reported, not auto-selected.  
5. CRS: **no reprojection**; mismatch only yields a warning string.  
6. NoData stats: from inspect lattice missing fraction (dataset-global), **not** AOI-masked valid cells.  
7. Flags: `exists`, `is_validated`, `is_activated`, `intersects_aoi`, `used_in_feature_application` (**always false**), `used_in_inference` (**always false**).

**Critical distinction (verified)**

| Measurement | Implemented? |
|-------------|--------------|
| Bounding-box intersection | **Yes** |
| Dataset footprint ≈ bbox of points/segments | **Yes** (inspect bbox) |
| Actual valid-cell coverage over AOI | **No** |
| % AOI covered by valid (non-NoData) measurements | **No** |

Code comments correctly call this “bbox-based only”. Acceptance/UI language saying “coverage” must be read as **spatial bbox intersection**, not true valid-data coverage. **MEDIUM** documentation/product-clarity gap (not a silent merge bug).

**Recommended action:** Rename UI labels to “bbox intersection”; keep valid-cell coverage as a future phase.

---

### Phase 4 — Lineament ingestion

| | |
|--|--|
| **Claimed** | COMPLETE |
| **Verified** | **PARTIALLY COMPLETE → treat claim as COMPLETE with gaps** |

**Evidence**

- Separate `asset_kind=vector_lineament`; not an XYZ measurement type.
- GeoJSON path works (tested).
- Shapefile ZIP: path-traversal blocked on zip entries; requires **fiona**.
- GeoPackage: service stages file then `load_gpkg_as_geojson` (also fiona); `try_load_vector_archive(.gpkg)` alone fails closed with `LINEAMENT_GPKG_STAGED` (by design if misused).
- CRS required at validate via `require_declared_crs`.
- Empty segments → WARN, not “no lineaments exist”.
- Density/distance derivation reuses `lineaments.py` / `feature_apply.apply_lineaments_to_dataset` (documented window default 500 m, m/m² and m).
- XYZ/DEM/gravity are not accepted as lineament uploads (`ASSET_KIND` / format checks).

**Gaps**

- Duplicate/suspicious feature detection: **not implemented**. **MEDIUM**.
- Geometry “repair” not performed (good); invalid/empty counted as WARN, originals immutable.
- Without fiona, GPKG/Shapefile uploads fail closed (documented). **INFO** in environments without fiona.
- Lineament apply assumes coordinates already in tile projected metres (existing shell contract). **INFO**.

---

### Phase 5 — Offline schema-v2 feature application

| | |
|--|--|
| **Claimed** | COMPLETE |
| **Verified** | **COMPLETE (with security/reproducibility gaps)** |

**Exact schema-v2 ordering** (`channel_schema.py` + `ml/constants.py`):

1. elevation  
2. slope  
3. plan_curvature  
4. profile_curvature  
5. twi  
6. relative_relief  
7. valley_depth  
8. ndvi  
9. ndwi  
10. clay_mineral_ratio  
11. iron_oxide_index  
12. gravity  
13. magnetics  
14. **overburden_thickness**  
15. **lineament_density**  
16. **lineament_distance**  

**Runtime import check (environment):** A background shell attempt to `import CHANNEL_NAMES_V2` via system `python` failed with `ModuleNotFoundError: No module named 'torch'`. This is an **environment/dependency limitation**, not an SSRI implementation defect. Classification: **NOT RUN / ENVIRONMENT BLOCKED**. Schema verification above rests on direct source inspection of `channel_schema.py` / `ml/constants.py` (and poetry pytest paths that already exercise `CHANNEL_NAMES_V2`), so the failed system-python import does **not** invalidate the 16-channel schema finding.

**Output evidence**

- `apply_geological_to_offline_dataset` → `apply_overburden_to_dataset` / `apply_lineaments_to_dataset`.
- Test `test_offline_apply_overburden_and_lineaments`: stack shape `[0] == len(CHANNEL_NAMES_V2)` (16); depth apply fails `APPLY_MEASUREMENT`.
- Missing cells: rasterize starts as `FEATURE_NODATA`; overburden sample leaves uncovered cells as nodata (NN only within 0.6× spacing — resampling, not inventing lattice holes as zero).
- Provenance: `geological_apply_report.json` with geo_ids, CRS, units conversion, window_m, sha256, `used_in_inference: false`.
- Conflict same measurement_type → `APPLY_CONFLICT`.
- Requires validated + activated.

**Gaps**

- **HIGH:** `POST /apply/offline` accepts `target_dataset_root` as a raw `Path` with **no** confinement under `output_root` / training storage. A principal with `RUN_INFERENCE` can direct writes outside the intended training tree if the process user can write there.
- `used_in_feature_application` in coverage summaries never flips after apply. **MEDIUM** honesty of status flags.
- Declared column mapping unused on validate/apply path if headers are nonstandard. **MEDIUM** (same as Phase 1).
- Reproducibility is good for geo_id + sha256 + params, but absolute `target_dataset_root` in the report can be host-specific. **LOW**.

**Recommended action:** Require `target_dataset_id` only, or resolve `target_dataset_root` through `TrainingStorage.resolve_under_training`.

---

### Phase 6 — Live v2 inference

| | |
|--|--|
| **Claimed** | BLOCKED |
| **Verified** | **BLOCKED (claim supported)** |

| Gate item | Evidence | Pass? |
|-----------|----------|-------|
| Schema v2 exists | `CHANNEL_NAMES_V2` length 16 | Yes |
| Ordering documented | `FEATURE_SCHEMA_V2.md`, `channel_schema.py` | Yes |
| Offline 16-ch stacks | Phase 5 + apply tests | Yes (offline) |
| Defensible client semantics for all 3 channels | Client CRS/Z unconfirmed; lineaments optional | No |
| Architecture default 16 | `architecture/config.py` `in_channels=CHANNEL_COUNT` (13) | No |
| Safety accepts only matching | `inference/safety.py` requires `CHANNEL_COUNT` | Blocks mismatched 16 into v1 loader |
| Trained schema-tied v2 checkpoint | No evaluated 16-ch production checkpoint found | No |
| Evaluation / held-out / calibration docs for v2 | Absent as production evidence | No |
| Separate versioned v2 inference path | Not implemented as geological Phase 6 | No |

**Pre-existing note (not introduced by geological work; `assess.py` not in geological diff):** assess offline feature loader already allows C∈{13,16}. Live AOI still uses `build_feature_stack` via `acquisition.py` and does **not** call the geological catalogue. Geological activation cannot silently change live AOI tensors.

---

## AOI coverage verdict

**Bounding-box matching only.**  
Not geometric polygon footprint beyond the axis-aligned bbox of uploaded points/segments.  
**Not** actual valid-data / non-NoData cell coverage of an AOI.  
Percentages are bbox-area ratios and can overstate usable science where gaps/negatives exist inside the bbox.

---

## Offline feature application verdict

Produces real **16-channel** `feature_stack.npy` updates via existing `feature_apply`, preserving CHANNEL_NAMES_V2 order and FEATURE_NODATA semantics for uncovered cells, with an on-disk apply report. Depth cannot enter overburden thickness. Constrained by the HIGH path-scoping issue and unused column overrides.

---

## Production safety verdict

**Isolated for the geological catalogue.**

- Live acquisition: `assess._resolve_features` → `acquire_feature_array_for_bbox` → `build_feature_stack` — no geological imports.
- `git diff HEAD` does **not** include `assess.py`, `inference/safety.py`, or `architecture/config.py`.
- Safety still enforces 13-channel model `in_channels`.
- Coverage/apply payloads set `used_in_inference: false`.
- Three hazards (subsidence / landslide / sinkhole) not renamed or removed by this work.

Caveat: offline assess with a user-supplied **16-channel** `.npy` remains a pre-existing assess contract; it is not driven by geological activation.

---

## Security verdict

| Control | Status |
|---------|--------|
| Auth deps on routes | Present (`require_run_inference` writes; `require_read_status` reads) |
| Auth off in development | Matches platform pattern (`development_principal` OPERATOR when auth disabled) |
| Viewer vs operator | Viewer: list/get/coverage/original; Operator+: upload/declare/validate/activate/apply — **stricter for writes** |
| Per-dataset ownership | **Absent** — any authorized principal sees all catalogue rows |
| Upload size | `reject_if_upload_too_large` |
| Path traversal on geo_id paths | `resolve_under` |
| Zip path traversal (shapefile) | Checked for `..` / absolute |
| Symlink handling | Not specially hardened beyond extract to temp |
| Filename sanitization | `safe_filename` |
| Original overwrite | Blocked after first upload |
| Path leakage in API `to_dict` | Relpaths stripped; `has_original`/`has_working` only |
| **`target_dataset_root` scoping** | **HIGH gap** |
| Original download authz | Requires `READ_STATUS` (any viewer with status read can download originals of any dataset) |

No destructive production penetration tests were run (per audit rules).

---

## Phase 6 readiness verdict

**Not ready.** No compatible, schema-tied, scientifically evaluated 16-channel production checkpoint was evidenced. Gate remains **BLOCKED**. Do not implement live v2 inference from this audit.

---

## Findings register

| ID | Severity | Location | Evidence | Consequence | Recommended correction |
|----|----------|----------|----------|-------------|------------------------|
| F1 | **HIGH** | `api/routes/geological.py` `apply_offline` | `Path(body.target_dataset_root)` used without confinement | Authenticated operator can write schema-v2 stacks outside intended storage root | Require `target_dataset_id` or resolve under training root |
| F2 | **MEDIUM** | `geological/validate.py` | Column args discarded (`_ = …`) | Declared non-default XYZ columns ignored at validate | Pass columns into ingest / rewrite working CSV |
| F3 | **MEDIUM** | `geological/coverage.py` + FE coverage UI | Bbox area ratio only | Operators may treat bbox % as valid-data coverage | Rename/clarify; defer valid-cell metrics |
| F4 | **MEDIUM** | `geological/models.py` / storage | No `user_id` / ACL | Shared catalogue among all authenticated users | Add ownership when auth multi-tenant required |
| F5 | **MEDIUM** | `coverage.dataset_coverage_summary` | `used_in_feature_application` hard-coded `False` | Status flag never reflects offline apply | Update from apply provenance or drop flag |
| F6 | **MEDIUM** | FE detail / list | No `index.jsonl` history UI | Architecture “history” incomplete | Expose append-only events |
| F7 | **MEDIUM** | `lineament_ingest.py` | No duplicate-feature analysis | Claimed validation item missing | Add optional duplicate/suspicious checks |
| F8 | **LOW** | FE `page.tsx` AOI CRS default `EPSG:32631` | Soft CRS hypothesis in UI | Bias toward unconfirmed CRS | Default empty |
| F9 | **LOW** | FE tests | No geological page tests | Regressions less visible | Add smoke tests later |
| F10 | **INFO** | Upload race | Check-then-write without lock | Rare double-write race | Atomic create flag / lock |
| F11 | **INFO** | GPKG/SHP | Requires fiona | Formats fail closed without dependency | Document ops requirement |
| F12 | **INFO** | Pre-existing `assess.py` C=16 offline | Unrelated to geological catalogue wiring | Offline 16-ch assess possible with matching checkpoint | Keep Phase 6 gate; do not confuse with catalogue activation |

No CRITICAL findings confirmed.

---

## Test evidence (independently executed)

Working directory for backend: `C:\Users\LENOVO\Documents\MrBusoye\ssri\model`  
Working directory for frontend: `C:\Users\LENOVO\Documents\MrBusoye\ssri\frontend`

| Command | Exit | Passed | Failed | Skipped | Notes |
|---------|------|--------|--------|---------|-------|
| `poetry run pytest tests/test_geological_ingest.py -q --tb=line` | 0 | **15** | 0 | 0 | Matches acceptance claim |
| `poetry run pytest tests/test_feature_apply_and_upload_unlimited.py tests/test_hazard_factors_v2.py tests/test_manual_training.py tests/test_assess_conditioning.py -q --tb=line` | 0 | **30** | 0 | 0 | Matches claim |
| `poetry run pytest tests/test_geological_ingest.py tests/test_feature_apply_and_upload_unlimited.py tests/test_assess_conditioning.py -q --tb=line` | 0 | **24** | 0 | 0 | Matches claim |
| `npm run typecheck` | 0 | — | — | — | PASS |
| `npm run lint` | 0 | — | — | — | PASS (`npm warn Unknown env config "devdir"` only) |
| `npm test` | 0 | **31** | 0 | 0 | PASS |
| `npm run build` | 0 | — | — | — | PASS; routes include `/geological` |
| System `python -c` import of `CHANNEL_NAMES_V2` | 1 | — | — | — | **NOT RUN / ENVIRONMENT BLOCKED** — `No module named 'torch'` on system interpreter; not an application test failure |

**Not run:** full `poetry run pytest` suite (acceptance also skipped it; time/scope). Limitation: broader regressions outside the listed files were not re-proven in this audit.

**Environment note:** Git inspection completed successfully (HEAD `2890838`; status retrieved). The torch-blocked import does not change schema or test verdicts above.

**Coverage quality:** Geological tests include failure paths (CRS missing, depth apply, irregular grid, activation warnings, conflicts, immutability). They do **not** cover column-override wiring, arbitrary `target_dataset_root` abuse, or multi-user ACL.

Synthetic fixtures only; not scientific evidence.

---

## Git state (preservation)

Initial and final working trees match aside from **addition of this audit report** as an untracked file. Existing modified/untracked user and implementation files were not staged, deleted, reset, rebased, amended, or pushed.

---

## Summary for operators

1. **Report location:** `SSRI_GEOLOGICAL_INDEPENDENT_AUDIT_REPORT.md`  
2. **Verdict:** **VERIFIED WITH GAPS**  
3. **Critical findings:** none  
4. **High findings:** F1 (`target_dataset_root` path scoping)  
5. **Tests:** 15 / 30 / 24 backend commands matched; FE typecheck/lint/31 tests/build passed  
6. **Phase 6:** remains **BLOCKED**  
7. **Git:** HEAD `2890838`; implementation still uncommitted; no push/deploy  

Await explicit approval before any remediation commits, push, deploy, or Phase 6 work.
