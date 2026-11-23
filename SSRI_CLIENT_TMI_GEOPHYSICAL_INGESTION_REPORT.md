# SSRI — Client Geophysical (TMI) Data Ingestion Report

**Date:** 2026-11-21  
**Scope:** Secure client TMI CSV/ZIPCSV ingest, validation, optional gridding, provenance, and 13-channel compatibility assessment.  
**Status:** Infrastructure complete. Client-specific suitability remains **unverified** until the real client CSV is supplied and reviewed.  
**Scientific validation:** `NOT_VALIDATED` (unchanged).  
**Production checkpoint:** Remains blocked (no Stage 2.5 three-class non-synthetic training package).

---

## 1. Existing ingestion architecture

Reused the **geological catalogue** (`model/src/ssri_model/geological/`), not a parallel pipeline:

| Component | Role |
|-----------|------|
| `GeologicalService` / `GeologicalStorage` | Create, upload, declare, validate, activate |
| `inspect_point_grid_bytes` | Structural CSV inspect |
| `validate_declared_point_grid` | Routes overburden/depth via release-shell lattice validator; **TMI via dedicated validator** |
| API `/api/v1/geological/*` | Auth via `manage_geological` / `read_status` |
| Frontend `/geological` | Operator upload + declare UI |

Stage 2.5 training zip ingest and platform Supabase training storage were **not** extended for scientific survey files.

---

## 2. Storage implementation

| Requirement | Implementation |
|-------------|----------------|
| Private storage | Filesystem under `{SSRI_API_OUTPUT_ROOT}/geological/{geo_id}/` |
| Original preserved | `original/{filename}` written once; `ORIGINAL_IMMUTABLE` on re-upload |
| Unique paths | Per-`geo_id` directories |
| No Cloudinary | Not used |
| No CSV-as-DB-rows | Object/files + JSON catalogue records |
| Service-role key in frontend | Not used; geological mutations use operator API key / session |

### Supabase Storage gap (documented, not worked around unsafely)

The platform stack uses Supabase for **accounts / platform training product records**. Geological geospatial originals are **filesystem-backed** via `build_geological_storage` (object backends are refused for this catalogue). Extending geological datasets into Supabase Storage would require a new secure server-side storage adapter; that was **not** implemented as an unsafe client-side workaround. API responses now state `storage_backend: filesystem_private_under_output_root`.

---

## 3. Upload workflow

1. `POST /geological/datasets` — create shell (`point_grid_csv`).
2. `POST /geological/datasets/{id}/upload` — CSV or ZIPCSV.
3. ZIPCSV: original zip preserved; exactly one CSV extracted to `working/layer.csv` (path-traversal rejected).
4. `POST .../declare` — measurement `total_magnetic_intensity` (aliases: `tmi`, …), CRS, units, column map, optional survey metadata.
5. `POST .../validate` — structural / coordinate / TMI / spatial report.
6. Optional `POST .../process` — nearest-neighbour grid → `working/derived/tmi_grid.tif` + provenance JSON.
7. Optional `POST .../compatibility` — `accepted_with_limitations` | `rejected`.
8. Activation: `reporting_only` allowed; **`approved` blocked for TMI** (`TMI_NOT_APPROVABLE`).

Missing survey metadata is stored as explicit `unknown` when the operator submits blank fields — never fabricated as real values.

---

## 4–6. Validation, geospatial checks, TMI statistics

Implemented in `ssri_model.geological.tmi`:

- Required columns + numeric parse + missing/duplicate counts  
- Geographic range checks for EPSG:4326 family  
- Rejection when declared geographic CRS but coordinates look like projected metres  
- TMI min/max/mean/stdev/percentiles/IQR outliers/constant detection  
- Units recorded; **nT is never assumed**  
- Extent, point count, density hints, lattice vs irregular cloud  
- Irregular clouds **WARN** (not FAIL) for catalogue validation; gridding is a separate gate (`can_process`)  
- Failed validation → `validation_status=failed` → processing blocked  

Synthetic fixture summary (`tests/fixtures/geological/tmi_client_xy_z.csv`, software-only):

| Metric | Value (fixture) |
|--------|-----------------|
| Points | 12 |
| CRS under test | EPSG:4326 |
| Units | unknown |
| Overall | PASS/WARN (irregular cloud) |
| `can_train` | false |

---

## 7. Processing capabilities

| Supported | Not performed automatically |
|-----------|-----------------------------|
| Nearest-neighbour point→raster | Reduction to the pole |
| Resolution / extent / NoData | Upward continuation |
| CRS on GeoTIFF tags | Regional–residual separation |
| Full processing provenance JSON | Treating raw TMI as residual anomaly |

Every derived product records source id, method, parameters, CRS, resolution, nodata, software/version, timestamp. Original bytes are never overwritten.

---

## 8. Feature compatibility assessment

Stage 2.5 contract (`CHANNEL_NAMES`, 13 channels): channel **`magnetics`** is **EMAG2 GeoTIFF**, not client survey TMI.

| Question | Finding |
|----------|---------|
| Corresponds to existing channel? | **No** (related name only) |
| Additional 14th channel? | **Not allowed** without architecture RFC |
| Replace magnetics? | **No** |
| Needs interpolation/resample? | Usually yes for irregular surveys |
| Live hazard contribution? | **False** |
| Hazard labels from TMI? | **Forbidden** |
| Production model | **Unchanged** |

Compatibility status defaults to `feature_compatibility_review`. Acceptance is at most `accepted_with_limitations` (catalogue/research), never Stage 2.5 training-ready.

---

## 9. Dataset registration and provenance

Tracked on `GeologicalDatasetRecord`: geo_id, filename, sha256, source, storage relpaths, CRS, column mapping, units, coverage, validation/processing status, derived relpath, feature_compatibility, provenance dict, timestamps, `scientific_validation_status=NOT_VALIDATED`.

Lifecycle signals used: uploaded/inspected → validated | validation failed → processing → processed → feature compatibility review → accepted_with_limitations | rejected.

**Valid CSV ≠ training-ready.**

---

## 10. Security

- Mutations require `manage_geological`  
- Original download authenticated  
- Upload size limits reused  
- ZIP path traversal rejected  
- No service-role keys in frontend  
- Catalogue remains single-tenant shared-operator (existing tenancy model)  

---

## 11. Test results

| Suite | Result |
|-------|--------|
| `tests/test_geological_tmi.py` | **10 passed** |
| Geological regression (ingest + TMI + acceptance + durability + remediation) | **53 passed, 1 skipped** |

Fixtures are **synthetic for software correctness only** — not scientific evidence.

---

## 12. Outstanding scientific requirements

1. Supply and review the **real client TMI CSV** (coverage, units, survey parameters).  
2. Authoritative **three-class hazard inventories** (subsidence, landslide, sinkhole) remain missing — **Stage 2.5 training gate stays blocked**.  
3. Do not convert TMI to hazard labels or positive/negative samples without independent ground truth.  
4. Any future use of client magnetics in the model requires an explicit architecture/training/evaluation RFC (not implemented here).  
5. Optional: Supabase Storage adapter for geological originals if multi-node private object storage is required.  
6. Production checkpoint promotion remains disqualified until a non-synthetic three-class Stage 2.5 package exists.

---

## Definition of done (checklist)

| Criterion | Met |
|-----------|-----|
| Secure receive client geophysical CSV/ZIPCSV | Yes (infrastructure) |
| Preserve originals | Yes |
| Validate geographic + measurement properties | Yes |
| Traceable processed outputs | Yes (optional grid) |
| Register provenance | Yes |
| Assess 13-channel compatibility | Yes (review gate) |
| Model unchanged | Yes |
| Production checkpoint blocked | Yes |
| Client-specific suitability verified | **No — awaiting real client file** |
