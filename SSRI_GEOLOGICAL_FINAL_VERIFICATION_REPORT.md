# SSRI — Final Geological Remediation Verification Report

**Mode:** READ-ONLY independent verification of F1–F5 remediation  
**Date:** 2026-11-20  
**Sources checked:** live source under `model/` and `frontend/`, tests, fixtures — not the remediation report alone  
**Baseline HEAD:** `28908383555136d63dc7d15283472850e1a456c8`  
**Only file created by this verification:** this report  

---

## Executive verdict

| Finding | Classification |
|---------|----------------|
| **F1** Filesystem security (HTTP) | **VERIFIED** |
| **F1** In-process library path | **VERIFIED WITH LIMITATIONS** |
| **F2** Column mappings | **VERIFIED WITH LIMITATIONS** |
| **F3** Coverage semantics | **VERIFIED** |
| **F4** Tenancy / access model | **VERIFIED** (multi-tenant isolation **not** implemented — intentional) |
| **F5** Provenance | **VERIFIED WITH LIMITATIONS** |
| Production 13-channel isolation | **VERIFIED** |
| Phase 6 | **BLOCKED** (confirmed) |

No **FAILED** or **NOT VERIFIED** classifications for F1–F5 remediation claims that were in scope. Remaining items are documented limitations, not remediation regressions.

---

## Repository state

| | Initial | Final |
|--|---------|-------|
| Root | `C:/Users/LENOVO/Documents/MrBusoye/ssri` | Same |
| Branch | `main` | `main` |
| HEAD | `2890838…` | `2890838…` |
| Staging | Nothing staged | Nothing staged |
| Production triad diffs vs HEAD | none for `assess.py` / `safety.py` / `architecture/config.py` | Unchanged |

Pre-existing modified/untracked work preserved. No commit, push, deploy, reset, or amend. This verification added only `SSRI_GEOLOGICAL_FINAL_VERIFICATION_REPORT.md` (untracked).

---

## F1 — Filesystem security

**Classification: VERIFIED (HTTP) / VERIFIED WITH LIMITATIONS (library)**

### HTTP request path (traced)

1. `POST /api/v1/geological/apply/offline` → `apply_offline` in `model/src/ssri_model/api/routes/geological.py`
2. Auth: `Depends(require_run_inference)`
3. `resolve_offline_apply_target(TrainingStorage, target_dataset_id, target_dataset_root)`
4. `TrainingStorage.get_dataset(dataset_id)` → registered metadata only
5. `training.resolve_under_training(ds.root_path)` → must stay under `{output_root}/training`
6. Extra check: resolved path must be under `training.datasets_dir`
7. Optional `target_dataset_root`: only if `resolve_under_training(root) ==` registered root; else `UNSAFE_PATH`
8. Resolved `Path` passed into `apply_geological_to_offline_dataset(..., target_dataset_root=target_root, target_dataset_id=…)`

### Controls verified in source

| Attack / case | Evidence | Result |
|---------------|----------|--------|
| Missing id / root-only | `APPLY_TARGET_ID_REQUIRED` | Rejected |
| `../` or `/` in id | `UnsafePathError` before lookup | Rejected |
| Absolute path as id | `Path(dataset_id).is_absolute()` | Rejected |
| Unknown id | `DatasetNotFoundError` | Rejected |
| Compat root mismatch | compare resolved paths | Rejected |
| Canonical confinement | `relative_to(datasets_dir)` | Enforced |

### Alternative API routes

Repo search for geological offline apply: only `POST /geological/apply/offline` accepts catalogue apply destinations. Separate release-shell routes (`/datasets/{dataset_id}/overburden/apply`, `…/lineaments/apply`) use registered `dataset_id` path params — not arbitrary host destinations via the geological catalogue.

### HTTP vs in-process

`apply_geological_to_offline_dataset` in `geological/apply.py` still accepts any `target_dataset_root: Path | str` for trusted callers/tests. **HTTP no longer exposes that.** Limitation is intentional and documented; not an HTTP regression.

### Symlink

`Path.resolve()` + `relative_to(training root)` rejects destinations that resolve outside training. Remediation test `test_f1_symlink_escape_rejected_where_supported` may **skip** when OS blocks symlink creation (observed: 1 skipped in verification run).

### Test evidence

`poetry run pytest tests/test_geological_remediation.py tests/test_geological_ingest.py -q --tb=line` → **28 passed, 1 skipped** (this verification).

---

## F2 — Column mappings

**Classification: VERIFIED WITH LIMITATIONS**

### Lifecycle (source-traced)

| Stage | Behavior |
|-------|----------|
| Inspect/upload | `service.upload_csv` may set detected column **indices** from inspect |
| Declare | `service.declare` stores explicit `x_column` / `y_column` / `z_column` on the record |
| Validate | `validate_declared_point_grid` → `assert_column_mapping_consistent` → `validate_point_grid_layer(..., x/y/value_column=…)` → `ingest_point_grid_csv` |
| Offline apply | `apply.py` re-reads **original** bytes with `rec.x_column` / `y_column` / `z_column` into `ingest_point_grid_csv` |

Shell engine remains the single CSV parser (`point_grid_csv.py`). Depth cannot enter overburden apply (`APPLY_MEASUREMENT`) — tested.

### Fixture

`model/tests/fixtures/geological/nonstandard_headers.csv`: headers `Easting_m`, `Northing_m`, `Thickness_m`, `Notes`.

### 16-channel / NoData

Apply path uses `feature_apply.apply_overburden_to_dataset` → stack expanded to `len(CHANNEL_NAMES_V2)` (16); channel index `overburden_thickness` = 13; uncovered cells remain `FEATURE_NODATA` per `feature_apply.py`.

### Limitation

Remediation tests assert validate/apply **PASS**, `column_mapping` recorded, and stack **shape** `[16,…]`. They do **not** assert that raster values at known cells equal `Thickness_m` (10/11/12) versus the unused `Notes` column. Mapping wiring is confirmed in code; independent pixel-value proof is incomplete.

Also: default name heuristics still apply when mappings are `None` (unchanged). Explicit mappings are not discarded (prior defect fixed).

---

## F3 — Coverage semantics

**Classification: VERIFIED**

### API (`geological/coverage.py`)

- `coverage_metric = "aoi_bbox_intersection"`
- Description states bbox intersection is **not** valid-cell / non-NoData AOI coverage
- Canonical field: `aoi_bbox_intersection_fraction`
- Back-compat alias: `approx_aoi_coverage_fraction` (same value)
- `dataset_footprint_bbox` present
- Math in `classify_coverage` unchanged (AABB intersection)
- CRS mismatch still yields `crs_warning`

### UI (`frontend/app/geological/page.tsx`)

- Title: “AOI bounding-box intersection”
- Copy explicitly: not valid-cell / non-NoData coverage
- Button: “Query bbox intersection”
- Displays `coverage_metric` and “not valid-data percentages”

No invented valid-cell percentage found in API or UI copy for this probe.

---

## F4 — Tenancy and access control

**Classification: VERIFIED**

### Declared model

`GEOLOGICAL_TENANCY_MODEL = "single_tenant_shared_operator_catalogue"` on create/list/get responses (`api/routes/geological.py`). List includes note that `created_by_key_id` is audit-only.

### `created_by_key_id`

Set from `principal.key_id` on create; stored on `GeologicalDatasetRecord`; **not** used to filter list/get/download/coverage/apply. **Not an ACL.**

### Role gates (all geological routes)

| Route | Dependency |
|-------|------------|
| create, upload, declare, validate, activation, apply/offline | `require_run_inference` |
| list, get, original download, coverage | `require_read_status` |

No geological route found without an auth dependency. When auth is disabled, platform `development_principal` still applies (existing pattern — not a geological bypass unique to this catalogue).

### Multi-tenant isolation

**Not implemented.** Any principal with `READ_STATUS` can list/get/download any catalogue dataset; any with `RUN_INFERENCE` can mutate/apply. This matches the remediation decision and training-storage pattern. Do not treat `created_by_key_id` as isolation.

---

## F5 — Provenance

**Classification: VERIFIED WITH LIMITATIONS**

### Success path

1. Apply completes all steps  
2. Writes `geological_apply_report.json` under target (includes `used_in_inference: false`)  
3. Appends per-geo_id rows to `{output_root}/geological/feature_applications.jsonl` via `record_feature_application` (requires `overall == PASS`)  
4. Coverage/get use `feature_application_status(record)` matching `geo_id` + `content_sha256`

### Failure path

Exceptions during apply occur **before** ledger append → `used_in_feature_application` stays false (tested with depth→thickness).

### Repeated applications

Each success appends another JSONL line; count increments (tested).

### Restart

New `GeologicalStorage` handle on same root re-reads JSONL (tested).

### `used_in_inference`

Hard-coded `False` in apply report, ledger payload, and coverage summaries.

### Limitations (confirmed in source)

1. **Crash window:** Feature stacks are mutated during `apply_*_to_dataset` **before** ledger append. A crash after stack write / after on-disk apply report but before JSONL append leaves offline outputs updated while catalogue status may still say never applied.  
2. **Concurrent append:** `open(..., "a")` without cross-process locking; interleaved writers are an unverified risk under parallel apply.  
3. **Empty SHA edge:** If `content_sha256` were empty, status falls back to geo_id history; normal uploads set SHA so this is rare.

---

## Production isolation

**Classification: VERIFIED**

| Check | Evidence |
|-------|----------|
| `assess.py` vs HEAD | No git diff |
| `inference/safety.py` vs HEAD | No git diff; still requires `CHANNEL_COUNT` for model `in_channels` |
| `architecture/config.py` vs HEAD | No git diff; default `in_channels=CHANNEL_COUNT` |
| Production channel count | `CHANNEL_COUNT = len(CHANNEL_NAMES)` = **13** in `ml/constants.py` |
| Hazards | `SUPPORTED_LABELS` / Stage 2.5 contracts untouched by geological remediation |
| Live AOI tensors | `acquisition.py` has **no** geological imports; `assess` live path uses `acquire_feature_array_for_bbox` → `build_feature_stack` |
| Catalogue activation → live assess | No wiring found |

Pre-existing note (unchanged by remediation): offline assess may accept C∈{13,16} feature arrays; that is separate from geological catalogue activation and does not equal Phase 6 readiness.

### Phase 6

**BLOCKED.** No evidence of a schema-tied, scientifically evaluated 16-channel production checkpoint or live v2 inference path from this remediation.

---

## Test evidence (this verification)

Working directory: `C:\Users\LENOVO\Documents\MrBusoye\ssri\model`

```text
poetry run pytest tests/test_geological_remediation.py tests/test_geological_ingest.py -q --tb=line
→ exit 0; 28 passed, 1 skipped
```

Skipped: F1 symlink test when OS cannot create symlinks.

Full backend suite: **NOT RUN**. Frontend suite: **NOT re-run** in this verification pass (prior remediation run reported typecheck/lint/31 tests/build pass).

---

## Remaining risks (non-blocking for F1–F5 claim)

| Risk | Severity | Notes |
|------|----------|-------|
| In-process `apply_geological_to_offline_dataset` accepts raw paths | LOW (ops) | Not HTTP-exposed |
| Apply crash before ledger | MEDIUM (ops honesty) | Stack may update without status flip |
| Concurrent JSONL append | LOW–MEDIUM | No file lock |
| No pixel-value assert for mapped Thickness_m | LOW (test gap) | Code path passes columns |
| Multi-tenant data isolation absent | INFO | Explicit single-tenant model |
| Symlink test skipped on some hosts | INFO | Confinement still uses `resolve()` |

---

## Summary for operators

1. **Report:** `SSRI_GEOLOGICAL_FINAL_VERIFICATION_REPORT.md`  
2. **F1–F5:** remediation claims **supported** with the limitations above  
3. **Production 13-channel path:** isolated and unchanged  
4. **Phase 6:** still **BLOCKED**  
5. **Git:** HEAD `2890838`; existing work preserved; no commit/push  

Await approval before any further changes, commit, push, or deployment.
