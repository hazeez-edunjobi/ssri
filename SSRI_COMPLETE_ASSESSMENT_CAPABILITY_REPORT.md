# SSRI complete assessment capability report

Date: 2026-11-19  
Baseline audited: `2f97d39`  
Scope: hazards (subsidence / landslide / sinkhole), lineaments, overburden, GeoTIFF/signed URLs  
No production infrastructure changes. Redis/job-queue readiness blocker left untouched.

Final verdict: **COMPLETE WITH SCIENTIFIC LIMITATIONS**

---

## 1. Existing implementation (before this pass)

| Capability | Already present |
|------------|-----------------|
| Hazards | Stage 2.5 labels + selectable dashboard hazards; API `hazards` filter; shell per-hazard gates |
| Live assess | 13-channel Stage 2.5 acquisition (`build_feature_stack`) |
| Lineaments / overburden | Shell/training **apply** path only (`feature_apply.py`, schema v2) |
| GeoTIFF | Backend `produce_geotiff` → local/object storage signed URL in `spatial_output_url` |
| Location provenance | Assess response field from prior handover work |
| Frontend GeoTIFF UX | Checkbox only; **no download action** |
| Point lineament/overburden values | **Not** in assess response |

Audit detail: [assess hazards/GeoTIFF audit](aa44352a-91bd-452e-94e9-732479f82641).

---

## 2. Missing implementation (addressed vs remaining)

### Addressed in this pass

- Conditioning-feature sampling on assess (`conditioning_features`)
- Honest unavailable/NoData reporting for overburden & lineaments
- GeoTIFF download link + expiry/CRS/georef metadata in UI and HTML report
- Acquisition-grid transform/CRS used for GeoTIFF when live meta provides it
- Feature attribution names for v2 channels (no anonymous `channel_13`)
- Shell assess profiles retain `primary_drivers` when available
- Dashboard copy clarifying live AOI is v1 (no live lineament/overburden acquire)

### Remaining (honest limits, not silent fabrications)

- Live AOI still acquires **13 channels only** — does not download lineaments/overburden from external providers
- Depth-to-interface is **not** auto-converted to overburden thickness
- GeoTIFF remains **first selected hazard only**
- Offline `.npy` without a matching acquisition transform still uses placeholder georef
- Scientific validation remains `NOT_VALIDATED`

---

## 3. Backend support for each hazard

| Hazard | Backend capability | Notes |
|--------|--------------------|-------|
| Subsidence | Yes (class 0) | Same Stage 2.5 multitask head |
| Landslide | Yes (class 1) | Same |
| Sinkhole | Yes (class 2) | Same (not liquefaction) |
| Independent validated models | **No** | Shared network; status stays NOT_VALIDATED |

Frontend only offers registry/fallback hazards that the backend supports. Unsupported hazards are not exposed as functional options.

---

## 4. Lineament integration status

| Path | Status |
|------|--------|
| Training/shell apply → schema v2 channels | Existing |
| Live assess acquisition | **Not acquired** |
| Assess response sampling | **Implemented** — `available` / `nodata` / `unavailable` |
| Fabrication / zero-fill | **Forbidden** — unavailable or NoData, never zero |

To include lineaments in scores: apply vectors in `/shell`, train/assess with a matching **v2** offline stack + checkpoint.

---

## 5. Overburden integration status

| Path | Status |
|------|--------|
| Training/shell apply (thickness) | Existing |
| Depth-to-interface auto-alias | **Rejected** (by design) |
| Live assess acquisition | **Not acquired** |
| Assess response sampling | **Implemented** with unit string stating thickness, not depth |
| Missing / uncertain provenance | Communicated as `unavailable` or `nodata` with reason |

---

## 6. GeoTIFF / signed URL status

| Item | Status |
|------|--------|
| Backend generation | Existing (`produce_geotiff`) |
| Signed / local URL | Existing (`spatial_output_url`) |
| Frontend download | **Added** (`assess-download-geotiff`) |
| Expiry messaging | **Added** |
| Missing artifact messaging | **Added** when URL absent |
| Georef | Uses acquisition transform/CRS when present; otherwise documents `placeholder_origin` |

Demo mode still does not produce GeoTIFF (null URL) — reported honestly in UI.

---

## 7. Frontend changes

- `AssessResultModal`: conditioning layers, drivers, GeoTIFF download / absence / expiry
- `lib/api.ts`: response types for conditioning + spatial metadata
- `lib/report.ts` (+ tests): conditioning + spatial sections
- `dashboard/page.tsx`: clearer v1 live vs v2 offline conditioning note

---

## 8. Backend changes

- `api/assess_conditioning.py` (new): sample overburden/lineament channels
- `api/routes/assess.py`: response fields; GeoTIFF meta; driver merge for shell profiles
- `api/acquisition.py`: pass projection transform into acquisition meta
- `api/demo_assessment.py`: unavailable conditioning (not zeros)
- `uncertainty/__init__.py`: v2 channel names in attribution

---

## 9. Test evidence

| Suite | Result |
|-------|--------|
| `test_assess_conditioning.py` | pass |
| `test_assess_geotiff_and_conditioning.py` | pass |
| `test_assess_location_provenance.py` / demo / audit / handover e2e (targeted) | pass |
| Frontend unit tests | 21 pass |
| Frontend typecheck / lint / production build | pass |

Synthetic fixtures only — not scientific validation.

---

## 10. Remaining scientific and deployment limitations

1. Shared Stage 2.5 model is **not** scientifically validated for any hazard.  
2. Live AOI does not acquire lineaments or overburden; those enter assess only via schema-v2 stacks.  
3. Production Redis/queue readiness remains a **separate** deployment blocker (`SSRI_PRODUCTION_DEPLOYMENT_VERIFICATION.md`).  
4. GeoTIFF covers the first selected hazard band only.  
5. Abeokuta / client CRS-units provenance still client-owned when using real layers.

---

## Verdict rationale

The assessment workflow now **honestly covers** the three supported hazards, surfaces lineament/overburden **when present** (and clearly when not), and exposes working GeoTIFF download when the backend returns a URL.

It is not “scientifically complete”: live acquisition of conditioning layers and independent validated hazard models are still out of scope. Hence:

**COMPLETE WITH SCIENTIFIC LIMITATIONS**
