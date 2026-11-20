# SSRI — Reusable Client Geological CSV Ingestion Architecture

**Mode:** Phased implementation proposal (design only — no production code changes in this document)  
**Date:** 2026-11-20  
**First milestone:** Reusable ingestion, validation, and dataset cataloguing  
**Production inference:** Stage 2.5 **v1 / 13 channels** remains unchanged  

This is a **multi-dataset** capability. `sheet 260_Abeokuta.csv` is one candidate example only. Do **not** hardcode Abeokuta CRS, Z meaning, spacing, or activation into production.

---

## 0. What already exists (reuse — do not duplicate)

| Capability | Location | Role |
|------------|----------|------|
| Delimiter/header/XYV parse, CRS require, grid spacing, gaps, duplicates, nodata | `model/src/ssri_model/release_shell/point_grid_csv.py` | Core CSV → `PointGridLayer` |
| Layer validation contract (CRS, gaps, measurement_type, units, negatives) | `model/src/ssri_model/release_shell/validator.py` → `validate_point_grid_layer` | PASS/WARN/FAIL report |
| Structural inspect (Abeokuta-hardcoded path today) | `poc/release_shell/scripts/inspect_client_csv.py` | Offline fact-finding; **generalize**, do not call from prod assess |
| Shell HTTP validate / overburden apply / lineament apply | `model/src/ssri_model/release_shell/routes.py` | Gated by `SSRI_RELEASE_SHELL`; operator tooling |
| Layer name normalization (no silent depth→thickness) | `model/src/ssri_model/release_shell/channel_schema.py` | `OVERBURDEN_THICKNESS`, `DEPTH_TO_BEDROCK`, aliases |
| Upload size/row guards + path safety | `manual_training/upload_limits.py`, `upload_io.py`, `ingest.py` | Reuse for geological uploads |
| Immutable dataset IDs + `dataset.json` filesystem catalogue | `manual_training/storage.py` | **Pattern** for new geological catalogue (separate root) |
| Platform product datasets (training zips/CSV → train runs) | `api/routes/platform.py`, `platform/service.py` | **Different product object** — do not overload |
| Stage 2.5 training datasets | `api/routes/training.py` | Supervised stacks only — do not overload |
| Frontend upload UX patterns | `frontend/app/training/page.tsx`, `lib/platformApi.ts` | Mirror for geological management UI (later phase) |
| Existing tests | `tests/test_feature_apply_and_upload_unlimited.py`, `tests/test_hazard_factors_v2.py` | Extend; do not fork validators |

**Non-goals for Milestone 1:** retrain, deploy, push, live assess channel changes, job-system rebuild, inventing lineaments from XYZ.

---

## 1. Product separation (critical)

Three catalogue families must stay distinct:

| Catalogue | Purpose | Feeds 13-ch inference? |
|-----------|---------|------------------------|
| **Geological layers** (this design) | Client XYZ / declared measurements | **No** (reporting / offline prep only until a future gated phase) |
| Stage 2.5 training datasets | 13-ch labelled stacks | Training only |
| Platform dataset versions | Product training uploads | Training runs |

Validated geological CSVs may later inform **reporting** and **offline feature prep**. They must **not** be injected into a v1 checkpoint tensor. Future 16-channel inference requires a compatible, evaluated **v2** checkpoint (existing live-v2 plan).

---

## 2. Target data model

### 2.1 Identity and measurement types

`measurement_type` is an **explicit operator declaration**, never inferred from filename alone.

Allowed identities (extensible enum / string registry):

- `overburden_thickness`
- `depth_to_bedrock` (aliases accepted only at declaration time: `depth_to_interface`, `bedrock_depth` → store canonical `depth_to_bedrock`)
- `other:<slug>` — requires free-text `measurement_description`; **never** auto-mapped into v2 channels

**Forbidden:** silent alias of depth → thickness; defaulting unknown Z to overburden.

### 2.2 Record: `GeologicalDatasetRecord`

Stored as `{output_root}/geological/datasets/{geo_id}/dataset.json`.

| Field | Type | Notes |
|-------|------|-------|
| `geo_id` | `geo_<12hex>` | Immutable; never reuse |
| `original_filename` | str | As uploaded |
| `display_name` | str | Operator-facing |
| `measurement_type` | str | Canonical identity |
| `measurement_description` | str | Required when type is `other:*` or unconfirmed |
| `x_column`, `y_column`, `z_column` | str \| int | Detected then operator-confirmed |
| `crs` | str \| null | EPSG/WKT; null until declared → cannot activate |
| `working_crs` | str \| null | Optional reprojection target |
| `units` | str \| null | e.g. `m`, `ft`; null until declared |
| `z_to_metres` | float \| null | Explicit conversion factor only |
| `coverage_bbox` | `[xmin,ymin,xmax,ymax]` | In declared CRS (and optionally WGS84 if transformable) |
| `grid_spacing_x`, `grid_spacing_y` | float \| null | File units |
| `grid_spacing_units` | `file_units` \| `metres` \| null | Metres only if client-confirmed |
| `nodata_policy` | object | See §4 |
| `source_client` / `provenance` | str / object | Client org, sheet id, notes |
| `uploaded_at` | ISO-8601 | |
| `validation_status` | `pending` \| `inspected` \| `validated` \| `failed` | |
| `validation_report` | object \| path | Last validate contract |
| `activation_status` | `inactive` \| `reporting_only` \| `approved` | Default `inactive` |
| `scientific_validation_status` | always `NOT_VALIDATED` for Milestone 1 | |
| `original_path` | relative path | Immutable bytes |
| `working_path` | relative path | Validated representation |
| `content_sha256` | str | Integrity + duplicate detection across uploads |

### 2.3 On-disk layout

```text
{output_root}/geological/
  datasets/
    {geo_id}/
      dataset.json                 # catalogue metadata
      original/
        {safe_original_filename}   # byte-identical upload; never mutate
      working/
        layer.csv                  # normalized UTF-8 working copy (optional column rename)
        inspect.json               # structural inspect (CRS may still be UNKNOWN)
        validate.json              # last validation report (requires declarations)
      coverage.geojson             # optional bbox polygon for AOI lookup (later)
  index.jsonl                      # append-only provenance log (upload/validate/activate events)
```

**Overwrite prevention:** each upload creates a new `geo_id`. Replacing working artifacts is allowed only within that id after re-validate; originals are never overwritten. Same `content_sha256` may be flagged as duplicate but still stored under a new id unless operator explicitly links versions.

---

## 3. Validation contracts

### 3.1 Two-stage pipeline

```text
Upload → preserve original → structural INSPECT → (operator declarations) → VALIDATE → catalogue status
```

| Stage | CRS required? | Measurement required? | Output |
|-------|---------------|----------------------|--------|
| **Inspect** | No | No | `inspect.json` (facts only; unknowns explicit) |
| **Validate** | Yes | Yes | `validate.json` + `validation_status` |

Reuse:

1. Generalize inspect logic from `inspect_client_csv.py` into a library function (path-parameterized; **no** hardcoded Abeokuta path).
2. Call existing `validate_point_grid_layer` / `ingest_point_grid_csv` for Validate.

### 3.2 Inspect contract (`GeologicalInspectReport`)

```json
{
  "overall": "INSPECTED",
  "delimiter": ",",
  "header_present": true,
  "header_row": ["X", "Y", "Z"],
  "detected_columns": {"x": 0, "y": 1, "z": 2},
  "row_count": 0,
  "bad_rows": 0,
  "blank_rows": 0,
  "duplicate_xy": 0,
  "x_range": [null, null],
  "y_range": [null, null],
  "z_range": [null, null],
  "z_stats": {"min": null, "max": null, "mean": null, "p01": null, "p50": null, "p99": null},
  "negative_z_count": 0,
  "sentinel_like": {},
  "dominant_spacing_x": null,
  "dominant_spacing_y": null,
  "grid_regularity_hint": "unknown|regular|irregular",
  "missing_lattice_cells": null,
  "gap_spatial_pattern": null,
  "crs": null,
  "measurement_type": null,
  "units": null,
  "messages": ["CRS unknown until operator declaration.", "Measurement meaning unknown."]
}
```

Negatives are **reported**, never auto-rejected at inspect.

### 3.3 Validate contract (extends existing shell report)

Reuse `validate_point_grid_layer` fields and add catalogue wrappers:

```json
{
  "overall": "PASS|WARN|FAIL",
  "can_train": false,
  "can_activate_reporting": false,
  "layer_name": "depth_to_bedrock",
  "measurement_type": "depth_to_interface",
  "units": "m",
  "crs": "EPSG:…",
  "working_crs": "EPSG:…",
  "checks": [
    {"name": "crs_declared", "status": "PASS|FAIL", "message": "…"},
    {"name": "measurement_type", "status": "PASS|FAIL", "message": "…"},
    {"name": "units_declared", "status": "PASS|WARN", "message": "…"},
    {"name": "grid_regular", "status": "PASS|FAIL", "message": "…"},
    {"name": "gaps", "status": "PASS|WARN", "message": "…"},
    {"name": "unit_sanity", "status": "PASS|WARN|FAIL", "message": "…"},
    {"name": "duplicates", "status": "PASS|WARN", "message": "…"},
    {"name": "spatial_coverage", "status": "PASS|WARN", "message": "bbox recorded"}
  ],
  "scientific_validation_status": "NOT_VALIDATED",
  "status": "FEATURE_LAYER_ONLY",
  "trainable": false
}
```

`can_activate_reporting` becomes true only when: overall ≠ FAIL, CRS set, measurement_type set, units set, activation still requires explicit operator action.

### 3.4 Nodata / negatives / gaps policy (catalogue defaults)

| Case | Policy |
|------|--------|
| Empty Z cell / known sentinel | `FEATURE_NODATA` (`-9999`); never zero-fill |
| Missing lattice cell | Remain absent → rasterize as `FEATURE_NODATA`; never interpolate |
| Negative + `overburden_thickness` | WARN/FAIL unit_sanity; block `approved` until policy acknowledged |
| Negative + `depth_to_bedrock` | WARN until client confirms physical negatives; else map to NoData via operator policy |
| Fabrication | Forbidden |

Store chosen policy on the record (`nodata_policy`); do not invent values.

### 3.5 CRS and units conversion process

1. Operator declares `crs` (and optional `working_crs`).
2. `require_declared_crs` (existing) parses EPSG/WKT.
3. Units: declare `units`; if not metres, set explicit `z_to_metres` (never guess).
4. Optional XY transform via existing pyproj path in `ingest_point_grid_csv`.
5. Persist conversion provenance on validate/activate events.
6. Spacing stays in **file units** until client confirms metre equivalence.

Hypotheses (EPSG:32631, 100 m, Z=overburden) remain **config candidates**, not code defaults.

---

## 4. API design (Milestone 1)

New router: `model/src/ssri_model/api/routes/geological.py`  
Mounted in `api/app.py` at `{api_prefix}` alongside training/platform.  
**Not** gated by `SSRI_RELEASE_SHELL` (product catalogue). Reuse auth deps already used by training (`require_run_inference` / platform actor — match existing training auth style; do not invent a new auth stack).

| Method | Route | Purpose |
|--------|-------|---------|
| `POST` | `/api/v1/geological/datasets` | Create catalogue entry (name, notes, optional declared fields) |
| `POST` | `/api/v1/geological/datasets/{geo_id}/upload` | Multipart CSV; preserve original; run **inspect**; write working copy |
| `GET` | `/api/v1/geological/datasets` | List (filter by measurement_type, activation_status, bbox later) |
| `GET` | `/api/v1/geological/datasets/{geo_id}` | Metadata + latest inspect/validate summaries |
| `POST` | `/api/v1/geological/datasets/{geo_id}/declare` | Set measurement_type, CRS, units, columns, nodata_policy |
| `POST` | `/api/v1/geological/datasets/{geo_id}/validate` | Run validate pipeline; persist report |
| `POST` | `/api/v1/geological/datasets/{geo_id}/activation` | `inactive` ↔ `reporting_only` (Milestone 1); reject `approved` for inference use |
| `GET` | `/api/v1/geological/datasets/{geo_id}/original` | Download original (authz) |
| `GET` | `/api/v1/geological/datasets/coverage` | Query which validated datasets intersect AOI bbox (**stub OK in M1**, full in Phase 3) |

### Request bodies (sketch)

**Create**

```json
{ "display_name": "Sheet 260 Abeokuta", "source_client": "…", "notes": "…" }
```

**Declare**

```json
{
  "measurement_type": "depth_to_bedrock",
  "measurement_description": "",
  "x_column": "X",
  "y_column": "Y",
  "z_column": "Z",
  "crs": "EPSG:32631",
  "working_crs": null,
  "units": "m",
  "z_to_metres": 1.0,
  "grid_spacing_units": null,
  "nodata_policy": {
    "missing_cells": "FEATURE_NODATA",
    "negatives": "report_only",
    "sentinels": [-9999, -999]
  }
}
```

**Activation**

```json
{ "activation_status": "reporting_only", "acknowledged_warnings": ["gaps", "unit_sanity"] }
```

Shell routes (`/layers/validate`, `/overburden/apply`, `/lineaments/apply`) remain for offline Stage 2.5 tile apply. Geological catalogue **does not** call apply in Milestone 1.

---

## 5. Module layout (exact files to add/change)

### Milestone 1 — create

| File | Responsibility |
|------|----------------|
| `model/src/ssri_model/geological/__init__.py` | Package export |
| `model/src/ssri_model/geological/models.py` | `GeologicalDatasetRecord`, enums, report TypedDicts |
| `model/src/ssri_model/geological/storage.py` | Catalogue I/O under `{output_root}/geological` (mirror `TrainingStorage`) |
| `model/src/ssri_model/geological/inspect.py` | Path-generic structural inspect (lift logic from `inspect_client_csv.py`) |
| `model/src/ssri_model/geological/validate.py` | Thin wrapper: declarations → `validate_point_grid_layer` + catalogue update |
| `model/src/ssri_model/geological/service.py` | Upload / declare / validate / list / activation orchestration |
| `model/src/ssri_model/api/routes/geological.py` | HTTP routes |
| `model/tests/test_geological_ingest.py` | Unit + API tests |
| `model/tests/fixtures/geological/` | Tiny synthetic XYZ CSVs (regular, gapped, negative, irregular) |

### Milestone 1 — modify (minimal)

| File | Change |
|------|--------|
| `model/src/ssri_model/api/app.py` | `include_router(geological.router, …)` |
| `poc/release_shell/scripts/inspect_client_csv.py` | Delegate to `geological.inspect` (keep CLI); remove hardcoded-only path as the library API |

### Explicitly do **not** change in Milestone 1

- `api/routes/assess.py`, `build_feature_stack`, `SSRIModel`, checkpoints  
- `feature_apply.py` production wiring  
- Job types / Celery  
- Frontend (Phase 2)  
- Abeokuta hypothesis JSON (may remain as a **sample declaration file**, not production defaults)

---

## 6. Lineament strategy (separate track)

Keep lineament ingestion **out of** XYZ CSV pipeline.

| Phase | Work |
|-------|------|
| M1 | Document only; catalogue schema may reserve `asset_kind: vector_lineament` without implementing upload |
| Phase 4 | Upload GeoJSON / GPKG / Shapefile (+ sidecar) with **required CRS**; store under `{geo_id}/original/`; inspect bbox/segment count via existing `load_lineament_segments` |
| Later | Derive density/distance with documented methods in `lineaments.py`; apply offline via shell; live AOI only per live-v2 plan |

**Never** invent lineament geometries from an XYZ grid.

---

## 7. Frontend plan (Phase 2 — after M1)

New surface (authorized operator): `/workspace/geological` or `/geological` under `PlatformShell`.

Flows:

1. Upload CSV → show inspect summary (columns, ranges, gaps, negatives).  
2. Declare measurement meaning, CRS, units (no silent defaults).  
3. Run validate → show check table.  
4. Coverage map/bbox readout.  
5. Activation badge: inactive / reporting_only / approved (approved greyed for inference).  
6. History list of prior uploads (immutable ids).

Reuse: `platformApi` multipart helpers, training page phase machine patterns.  
Do not put this on the public marketing site or alter `/dashboard` assess map in Phase 2 beyond a future “available layers for AOI” readout (Phase 3).

---

## 8. Assessment integration (later phases — constraints)

| Phase | Allowed use | Forbidden |
|-------|-------------|-----------|
| M1–2 | Catalogue + validate only | Any assess tensor change |
| Phase 3 | AOI coverage query; attach layer provenance to **reports** | Feeding extra channels into 13-ch checkpoint |
| Phase 5 | Offline shell apply onto **v2 training tiles** when declared thickness + CRS | Auto-apply depth as thickness |
| Phase 6 | Live 16-ch inference | Without evaluated v2 checkpoint + explicit flag |

Response honesty (when reporting attached): `available_at_location`, `used_in_inference: false` for v1.

---

## 9. Phased roadmap

### Phase 0 — Already done
Offline inspect script, shell validate/apply, provisional Abeokuta prep docs, channel honesty UI.

### Phase 1 — **First implementation milestone** (this proposal’s build target)
Reusable ingest + inspect + declare + validate + filesystem catalogue + API + tests.  
No frontend required to ship M1 (CLI/API sufficient).  
No inference changes. No deploy/push in this planning step.

**Acceptance criteria**

- [ ] Upload two different synthetic CSVs → two distinct `geo_id`s; originals intact  
- [ ] Inspect works without CRS  
- [ ] Validate fails closed without CRS / measurement_type  
- [ ] Depth declaration never stored as `overburden_thickness`  
- [ ] Gaps/negatives reported; no zero-fill in working rasterization helpers  
- [ ] List/get return metadata; activation defaults `inactive`  
- [ ] Existing `pytest` suites for assess/training still pass; new `test_geological_ingest.py` green  
- [ ] No Abeokuta constants in production modules  

### Phase 2 — Geological management UI
Frontend declare/validate/activate against Phase 1 API.

### Phase 3 — Coverage & reporting
AOI∩bbox query; attach selected layer provenance to PDF/report; still `used_in_inference: false`.

### Phase 4 — Lineament catalogue
Vector upload + CRS + inspect; separate from XYZ.

### Phase 5 — Offline feature prep bridge
Optional: validated `overburden_thickness` → shell `/overburden/apply` on non-production training roots only, with provenance.

### Phase 6 — Future live v2 (separate plan)
Only with evaluated 16-ch checkpoint; out of scope for M1.

---

## 10. Tests (Milestone 1)

| Test | Asserts |
|------|---------|
| `test_inspect_detects_delimiter_and_header` | Sniffer + columns |
| `test_inspect_reports_negatives_and_gaps` | Counts; no rejection |
| `test_upload_preserves_original_bytes` | SHA256 match |
| `test_upload_creates_unique_geo_ids` | No overwrite |
| `test_validate_requires_crs` | `CRS_REQUIRED` / FAIL |
| `test_validate_depth_not_aliased_to_thickness` | FAIL if mismatched |
| `test_validate_thickness_negative_warn` | unit_sanity WARN |
| `test_irregular_grid_fails` | `CSV_GRID` |
| `test_activation_defaults_inactive` | Cannot skip declare |
| `test_list_filters_measurement_type` | Catalogue query |
| `test_api_upload_inspect_validate_roundtrip` | FastAPI TestClient |

Fixtures: small regular 5×5 grids; one with a hole; one with negatives; one irregular spacing.

Reuse patterns from `test_hazard_factors_v2.py` for measurement_type contracts.

---

## 11. Client confirmations (per dataset, before activation)

Same spirit as Abeokuta prep, but **per upload**:

1. What does Z measure?  
2. Units of Z?  
3. CRS (EPSG/WKT)?  
4. Are X/Y projected? Meaning of negative X if any?  
5. Grid spacing units (metres vs file units)?  
6. Gap policy?  
7. Negative-value policy?  
8. Permission: reporting-only vs future model input?  
9. Lineament vectors available separately?

Until answered: `activation_status=inactive`.

---

## 12. Execution stance

- **Now:** this proposal only (no code/deploy/push).  
- **Next when approved:** implement Phase 1 files listed in §5 only.  
- Keep `SSRI_ABEOKUTA_PROVISIONAL_INTEGRATION_PREP.md` as a **worked example** of declarations, not as production config.

---

## Appendix A — Mapping to user requirements

| Requirement | Where addressed |
|-------------|-----------------|
| Multi-CSV uploads | Catalogue + unique `geo_id` |
| Detect delimiter/headers | `geological.inspect` ← `point_grid_csv` / inspect lift |
| Validate columns, ranges, spacing, dups, gaps | Inspect + Validate |
| Report negatives without auto-reject | Inspect contract |
| Preserve original + working copy | On-disk layout |
| Independent metadata / no silent alias | `GeologicalDatasetRecord` + declare |
| Validation pipeline | §3 |
| Catalogue + no overwrite + AOI identity | §2, coverage stub → Phase 3 |
| 13-ch unchanged | §1, §8 |
| Lineaments separate | §6 |
| Frontend plan | §7 |
| Reuse existing | §0 |
| First milestone = ingest/validate/catalogue | Phase 1 |
