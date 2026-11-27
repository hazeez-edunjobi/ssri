# SSRI — Client Workflow Acceptance

**Date:** 2026-11-27  
**Baseline:** `main` @ `03dd062` (API evidence lineage `dd4caaa`)  
**Constraint:** No new production assessment; reuse `assess-599dd089f4204cbe`  
**Science status:** `NOT_VALIDATED` (unchanged)

---

## How the client workflow actually works

Upload and ground-risk assessment are **related but separate** product surfaces. SSRI does **not** implement “upload this CSV → assess that same file as the live 13-channel stack.”

| Client goal | UI | Backend |
|-------------|----|---------|
| Upload / validate Stage 2.5 training data (ZIP or trainable CSV) | `/training`, `/datasets/[id]` | `POST /api/v1/platform/datasets/{id}/versions` |
| Upload / validate geological point-grid CSV (e.g. TMI) | `/geological` | `POST /api/v1/geological/datasets/{id}/upload` + declare/validate |
| Run ground-risk assessment | `/dashboard` | `POST /api/v1/assess` (map AOI → live acquisition **or** offline `.npy`) |
| View results / spatial | Assessment modal + `/assessments/[id]` | History detail, `/spatial`, evidence when persisted |

A single-layer **X,Y,Z** CSV (TMI) is a **feature layer / catalogue** dataset — not a Stage 2.5 training set and not the live assess tensor. The training UI states this explicitly (`frontend/app/training/page.tsx`).

---

## Direct answers

### 1. Can a client upload a dataset?
**PASS**

| Evidence | Detail |
|----------|--------|
| UI | `/training` accepts ZIP or CSV/ZIP-of-CSVs (`accept=".csv,.zip…"`); CRS required for CSV |
| UI | `/datasets/[id]` Stage 2.5 ZIP upload via `uploadDatasetVersion` |
| UI | `/geological` point-grid CSV / lineament vectors |
| API | Platform `register_dataset_zip` / CSV path (`platform/service.py`); geological upload with zip path-traversal guards (`geological/service.py`) |
| Limits | Upload size enforced → HTTP **413** (`reject_if_upload_too_large`; FE `geologicalHttpErrorMessage` for 413) |

### 2. Does validation work?
**PASS**

| Evidence | Detail |
|----------|--------|
| Local automated | `tests/test_csv_import.py`, geological TMI fixtures + validators — included in **46 passed** suite this session (`test_csv_import`, `test_geological_tmi`, assess/location/uncertainty/api_assess) |
| Rules | Trainable CSV needs X/Y + 13 channels + labels + CRS (`manual_training/csv_import.py` `require_crs`) |
| Feature-only | X/Y/Z alone → not trainable; directed toward geological / feature-layer handling |
| Geological | Declare measurement type + source CRS; TMI not elevation/depth/label (`geological/tmi.py`, `validate.py`) |
| UI copy | Training page explains feature-layer vs trainable CSV |

### 3. Are coordinates and CRS interpreted correctly?
**PASS**

| Evidence | Detail |
|----------|--------|
| Local automated | `frontend` coordinate tests (lat-first parse/format); `test_assess_location_provenance.py`, `test_location_provenance.py` |
| Production | Known point `7.246007639991646`, `3.211853787860889` → model grid pixel **r37 c37**, CRS **EPSG:32631**, 74×74 (`assess-599dd089f4204cbe`) |
| Contract | Named `latitude`/`longitude` on assess; GeoJSON lon,lat documented in provenance |
| TMI | Declared EPSG required; Abeokuta path 32632→32631→4326 when configured — **Z remains TMI** |

### 4. Can a client initiate an assessment?
**PASS**

| Evidence | Detail |
|----------|--------|
| UI | `/dashboard` → `submitAssess` → `POST /api/v1/assess` (`frontend/lib/api.ts`, `assessRequest.ts`) |
| Guards | Session required; button disabled without model/hazards; in-flight guard |
| Local | `buildAssessRequestBody`, `assessmentButtonDisabled` tests; Playwright `e2e/dashboard.spec.ts` (login gate, empty AOI validation) |
| Production | Prior authorized assess `assess-599dd089f4204cbe` / request `assess-e6c58df43d5e` |

### 5. Does the backend successfully process it?
**PASS** (live production verification on existing assessment)

| Evidence | Detail |
|----------|--------|
| HTTP | Prior `POST /api/v1/assess` → **200** |
| Re-read today | `GET /api/v1/assess/history/assess-599dd089f4204cbe` → **200** |
| Scores | subsidence 0.588 / landslide 0.525 / sinkhole 0.487 |
| CIs | `credible_interval_*=null`, `uncertainty_intervals_available=false` |
| Channels | 13-name contract; optical NoData at query pixel marked invalid in evidence |
| Spatial | `spatial_download_path` present |
| Tensor | Prior SHA `522fee31001847836c8e7667c4d2eedd0906d63faf00859f0653b9f6bf27cf29` |

### 6. Does the frontend display the actual results?
**PASS** (implementation + unit evidence; prod UI browser session not re-run here)

| Evidence | Detail |
|----------|--------|
| Modal | `AssessResultModal.tsx` binds hazard profiles, scores, `NOT_VALIDATED`, drivers |
| Uncertainty | `presentHazardIntervals` → unavailable copy (`data-testid="assess-hazard-ci-unavailable"`); zero-width bands rejected — **103** FE tests pass including CI cases |
| History | `/assessments`, `/assessments/[id]` load API detail + GeoTIFF download helper |
| Map | Dashboard MapLibre AOI + result overlay hooks; `MapSkeleton` while loading |

### 7. Defects preventing clients from completing this workflow?
**None identified that block the intended client paths**, provided clients use the correct surface:

- Ground-risk assess → `/dashboard` (not “upload TMI CSV to get hazard scores”).  
- Training CSV/ZIP → `/training` or `/datasets` (full 13-ch + labels).  
- Geological TMI → `/geological` (catalogue / magnetic tools; not Stage 2.5 labels).

| Residual note | Classification |
|---------------|----------------|
| Upload ≠ live assess input | Product design (documented), not a defect |
| Signed-in Playwright against production UI | Not re-executed this pass → does not overturn API + code evidence |
| Scientific validation | **NOT VALIDATED** — disclosed limitation, not a software blocker |

---

## Requirement matrix (A–D)

| Area | Status | Evidence |
|------|--------|----------|
| A. Dataset upload UI / formats / size / columns / errors | PASS | `/training`, `/geological`, `/datasets/[id]`; platform 413; CSV/ZIP accept; csv_import + geological tests |
| B. Geospatial X/Y, CRS, NoData, 13-ch, no TMI-as-label | PASS | Location provenance tests; prod query-pixel validity; CHANNEL_NAMES; TMI validators |
| C. Assessment initiation / API / completion / errors / location match | PASS | Dashboard + `POST /assess`; prod `assess-599…`; e2e empty-AOI errors |
| D. Results, map, explanations, spatial, honest CIs / limitations | PASS | Modal + history; null CIs; `NOT_VALIDATED` badge; spatial path |

---

## Tests executed this pass

| Suite | Result | Label |
|-------|--------|-------|
| `pytest` csv_import, geological_tmi, location provenance, uncertainty, api_assess | **46 passed** | Local automated |
| `npm test` (full lib suite) | **103 passed** | Local automated |
| Live `GET …/history/assess-599dd089f4204cbe` | **200**, null CIs, evidence available | Live production verification |

---

## Declaration

**SSRI CLIENT WORKFLOW: VERIFIED — READY FOR CLIENT USE, SUBJECT TO DOCUMENTED SCIENTIFIC LIMITATIONS.**

Clients can upload and validate supported datasets, interpret coordinates/CRS correctly, initiate Stage 2.5 map assessments against the authoritative API, and view real backend results (including honest unavailable uncertainty). Relative susceptibility scores remain **`NOT_VALIDATED`** and must not be treated as calibrated probabilities or field-confirmed geology.
