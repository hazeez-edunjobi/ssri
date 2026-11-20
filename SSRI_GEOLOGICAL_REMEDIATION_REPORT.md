# SSRI — Geological Remediation Report (F1–F5)

**Date:** 2026-11-20  
**Scope:** Targeted corrections for confirmed audit findings F1–F5  
**Baseline HEAD:** `28908383555136d63dc7d15283472850e1a456c8` (`main`)  
**Phase 6:** remains **BLOCKED**  
**Commit / push / deploy:** not performed  

---

## 1. Executive summary

Remediation for audit findings **F1–F5** is complete locally.

| Finding | Result |
|---------|--------|
| **F1** HIGH — arbitrary offline apply path | **Fixed.** API requires registered `target_dataset_id`; resolves via `TrainingStorage`; rejects traversal / absolute path ids / mismatched roots. |
| **F2** MEDIUM — ignored CSV column mappings | **Fixed.** Declared `x`/`y`/`z` columns pass through shell `ingest_point_grid_csv` / `validate_point_grid_layer` for validate and offline apply. |
| **F3** MEDIUM — coverage semantics | **Fixed.** API + UI explicitly label **AOI bbox intersection**; math unchanged; no invented valid-cell %. |
| **F4** MEDIUM — ownership / ACL | **Documented + audit field.** Intentional **single-tenant shared operator catalogue** (same as training storage). Records `created_by_key_id`; does not invent multi-tenant ACL. |
| **F5** MEDIUM — feature-application status | **Fixed.** Persisted `feature_applications.jsonl` drives `used_in_feature_application`; failed applies do not mark success; `used_in_inference` stays false. |

Production 13-channel inference path (`assess.py`, `inference/safety.py`, `architecture/config.py`) was **not** modified. All three hazards remain available. Phase 6 remains blocked.

---

## 2. F1–F5 implementation details

### F1 — Secure offline apply path resolution

- Added `resolve_offline_apply_target()` in `api/routes/geological.py`.
- Requires non-empty `target_dataset_id` matching `ds_[…]`.
- Rejects `..`, `/`, `\`, and absolute paths masquerading as ids (`UNSAFE_PATH`).
- Loads dataset via `TrainingStorage.get_dataset`, then `resolve_under_training(ds.root_path)`.
- Defense in depth: resolved path must remain under `training/datasets/`.
- Deprecated `target_dataset_root`: accepted **only** when it resolves to the same registered dataset root; otherwise `UNSAFE_PATH`.
- Root-only requests → `APPLY_TARGET_ID_REQUIRED`.

### F2 — Declared CSV column mappings

- Extended `validate_point_grid_layer` to accept and pass `x_column` / `y_column` / `value_column` into `ingest_point_grid_csv` (existing shell engine — no second CSV parser).
- `validate_declared_point_grid` no longer discards columns; adds `assert_column_mapping_consistent` for ambiguous duplicates.
- Offline `apply.py` passes the same declared mappings into ingest.
- Original CSV bytes remain immutable; working copy behavior unchanged except validation now uses declared mapping on original/working bytes.

### F3 — AOI bbox intersection semantics

- Coverage math (`classify_coverage`) unchanged.
- Response adds:
  - `coverage_metric: "aoi_bbox_intersection"`
  - `coverage_metric_description`
  - `aoi_bbox_intersection_fraction` (canonical)
  - `approx_aoi_coverage_fraction` retained as backwards-compatible alias
  - `dataset_footprint_bbox`
- Frontend `/geological` section retitled and copy updated to state bbox intersection ≠ valid-cell coverage.

### F4 — Ownership / tenancy decision

**Decision:** SSRI geological catalogue is a **single-tenant shared operator catalogue**, matching `TrainingStorage` (no per-dataset ACL filtering today).

Rationale: auth principals exist (`AuthenticatedPrincipal.key_id` / roles), but Stage 2.5 training datasets likewise lack owner-scoped list/get. Inventing incomplete multi-tenant ACL would change operator workflows without a platform tenancy model.

Implemented without weakening role gates:

- Record `created_by_key_id` on create (audit).
- Expose `tenancy_model: single_tenant_shared_operator_catalogue` on list/create/get.
- Keep role-based write vs read (`require_run_inference` / `require_read_status`).

### F5 — Feature-application provenance

- New append-only `{output_root}/geological/feature_applications.jsonl`.
- Successful apply records: `geo_id`, `content_sha256`, `target_dataset_id`, channels, params, timestamp, `overall=PASS`, `used_in_inference=false`.
- Failed applies raise before provenance write → status stays unapplied.
- `GeologicalStorage.feature_application_status()` derives boolean from persisted rows matched by `geo_id` + `content_sha256`.
- Coverage summaries use storage lookup (no hard-coded `False`).

---

## 3. Exact files changed

| Path | Change |
|------|--------|
| `model/src/ssri_model/api/routes/geological.py` | F1 resolve helper; F4 tenancy; F5 detail payload |
| `model/src/ssri_model/geological/apply.py` | Column mapping; provenance; `target_dataset_id` |
| `model/src/ssri_model/geological/coverage.py` | Bbox metric labels; provenance-aware status |
| `model/src/ssri_model/geological/validate.py` | Honor column mappings; ambiguity check |
| `model/src/ssri_model/geological/storage.py` | Feature application ledger; `created_by` |
| `model/src/ssri_model/geological/models.py` | `created_by_key_id` |
| `model/src/ssri_model/geological/service.py` | Create audit id; coverage passes storage |
| `model/src/ssri_model/release_shell/validator.py` | Pass column args into ingest |
| `frontend/app/geological/page.tsx` | Bbox intersection UI copy |
| `model/tests/test_geological_remediation.py` | New F1–F5 tests |
| `model/tests/test_geological_ingest.py` | Coverage metric assertions |
| `model/tests/fixtures/geological/nonstandard_headers.csv` | Synthetic mapped-header fixture |
| `SSRI_GEOLOGICAL_REMEDIATION_REPORT.md` | This report |

**Not modified:** `assess.py`, `inference/safety.py`, `architecture/config.py`, acceptance report, independent audit report (except this new remediation deliverable).

---

## 4. API contract changes

| Endpoint | Change |
|----------|--------|
| `POST /apply/offline` | **`target_dataset_id` required.** `target_dataset_root` optional compat-only (must match registered root). |
| `POST /coverage` | Adds `coverage_metric`, description, `aoi_bbox_intersection_fraction`; keeps `approx_aoi_coverage_fraction`. |
| `GET/POST /datasets*` | Adds `tenancy_model` (+ note on list). Create stores `created_by_key_id`. |
| `GET /datasets/{id}` | Adds `feature_application` provenance block. |
| Validation reports | Include `column_mapping` when applied. |

---

## 5. Storage and security behavior

- Geological root: `{output_root}/geological/`
- New ledger: `feature_applications.jsonl`
- Offline apply writes only under `{output_root}/training/datasets/{dataset_id}/…`
- Role gates unchanged; auth-off development principal still OPERATOR (platform pattern)

---

## 6. Ownership / tenancy decision

**`single_tenant_shared_operator_catalogue`**

Audit field `created_by_key_id` is recorded. List/get/download are **not** owner-filtered. Multi-tenant ACL is deferred until the platform adopts a consistent tenancy model for training + geological catalogues together.

---

## 7. Provenance implementation

Successful offline apply → append JSONL entry keyed by `geo_id` + `content_sha256` + `target_dataset_id` (not filename). Coverage `used_in_feature_application` reflects ledger. `used_in_inference` remains **false**.

---

## 8. Tests added

`model/tests/test_geological_remediation.py`:

- F1: registered id success; unknown id; traversal; absolute path; API root-only reject; mismatch reject; symlink escape where supported (skipped if OS blocks)
- F2: nonstandard headers validate+apply; missing column; ambiguous mapping; defaults; depth cannot apply as thickness
- F3: metric identity + CRS warning
- F4: tenancy_model + created_by on API create
- F5: success updates; failure does not; restart survival; repeat count; coverage reflects status

Fixture: `nonstandard_headers.csv` (`Easting_m`, `Northing_m`, `Thickness_m`).

---

## 9. Actual test results

### Backend

Working directory: `C:\Users\LENOVO\Documents\MrBusoye\ssri\model`

| Command | Exit | Result |
|---------|------|--------|
| `poetry run pytest tests/test_geological_ingest.py tests/test_geological_remediation.py -q --tb=line` | 0 | **28 passed, 1 skipped** |
| `poetry run pytest tests/test_feature_apply_and_upload_unlimited.py tests/test_hazard_factors_v2.py tests/test_assess_conditioning.py -q --tb=line` | 0 | **23 passed** |
| `poetry run pytest tests/test_manual_training.py::test_training_api_upload_validate_and_start -q --tb=short` | 0 | **1 passed** (one earlier combined run saw a transient `JOB_EXECUTION_FAILED`; re-run passed; unrelated to geological remediation) |

**Full backend suite:** NOT RUN (time/scope).

### Frontend

Working directory: `C:\Users\LENOVO\Documents\MrBusoye\ssri\frontend`

| Command | Exit | Result |
|---------|------|--------|
| `npm run typecheck` | 0 | PASS |
| `npm run lint` | 0 | PASS |
| `npm test` | 0 | **31 passed** |
| `npm run build` | 0 | PASS (includes `/geological`) |

Environment notes: npm `devdir` config warnings only; not application failures.

---

## 10. Remaining limitations

- F6–F9 not in scope (history UI, lineament duplicate detection, empty AOI CRS default, dedicated FE geological tests).
- Valid-cell AOI coverage still not implemented (intentionally deferred).
- Multi-tenant dataset ACL not implemented (explicit single-tenant decision).
- Symlink-escape OS coverage may skip on environments without symlink privilege.
- Library `apply_geological_to_offline_dataset(..., target_dataset_root=…)` remains callable in-process for tests/scripts; **HTTP API** no longer accepts arbitrary roots.

---

## 11. Production 13-channel isolation

Confirmed unchanged:

- `model/src/ssri_model/api/routes/assess.py` — no diff vs HEAD
- `model/src/ssri_model/inference/safety.py` — no diff vs HEAD
- `model/src/ssri_model/architecture/config.py` — no diff vs HEAD
- Live AOI acquisition not wired to geological catalogue
- Hazards: subsidence, landslide, sinkhole — contracts untouched
- Geological apply / coverage still set `used_in_inference: false`

---

## 12. Phase 6 readiness

**BLOCKED.** No schema-tied evaluated 16-channel production checkpoint. Remediation does not enable live v2 inference.

---

## 13. Git state

### Initial (remediation start)

- Branch: `main`
- HEAD: `2890838…`
- Existing modified/untracked geological implementation and docs present
- Nothing staged by this work

### Final

- HEAD unchanged: `28908383555136d63dc7d15283472850e1a456c8`
- Ahead/behind `origin/main`: even
- New/updated untracked or modified remediation files present (see §3)
- Pre-existing user/worktree files preserved
- **No** commit, push, reset, rebase, amend, or deploy

Await approval before commit, push, deploy, or further phases.
