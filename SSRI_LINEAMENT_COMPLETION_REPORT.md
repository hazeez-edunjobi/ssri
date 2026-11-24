# SSRI — Lineament Completion Report

**Date:** 2026-11-24  
**Dataset:** `geo_be00a34ad6f4` — Abeokuta TMI sheet 260  
**Status:** Candidate extraction **implemented and verified** · Scientific class **NOT_VALIDATED** · **not confirmed faults**

---

## Abeokuta source data assessment

| Item | Value |
|---|---|
| Source CSV | `data/outputs/geological/datasets/geo_be00a34ad6f4/original/sheet_260_Abeokuta.csv` |
| Rows (validated) | 308 153 numeric X/Y/Z |
| Measurement | `total_magnetic_intensity` (nT) |
| X / Y | Easting / Northing (not lon/lat) |
| Z | TMI — **not** elevation, depth, or overburden |
| Source CRS | EPSG:32632 |
| Processing CRS | EPSG:32631 |
| Display CRS | EPSG:4326 |
| Grid | 100 m, shape (554, 553), ~305 067 valid cells |

Publication-guided NE–SW structural orientation remains **contextual interpretation**, not independently confirmed fault mapping.

---

## CRS verification

Existing validation (`working/validate.json`) PASSes CRS and source-magnitude consistency for western Nigeria UTM. Processing artefacts are written in EPSG:32631. Candidate GeoJSON declares the same processing CRS.

---

## Processing methodology

Implemented in `ssri_model.geological.magnetic_lineament_extraction` (v1.0.0), orchestrated by `GeologicalService.extract_candidate_lineaments`, API `POST /api/v1/geological/datasets/{geo_id}/magnetic/lineaments`.

1. **Quality / gridding** — reuse validated TMI grid + mask (`tmi_grid_arrays.npz`).
2. **Enhancement** — prefer total horizontal gradient (`first_horizontal_derivative`); optional blend with `|TMI − Gaussian|`.
3. **Threshold** — percentile of valid enhancement (default P92).
4. **Edge / ridge** — morphological clean + skeletonisation.
5. **Vectors** — connected components → polylines; length/component filters.
6. **Stats** — length + undirected azimuth (0–180°) rose bins.
7. **Rasters** — EDT distance + box-filter density (documented approximation).
8. **Provenance** — QC JSON with checksums, params, limitations.

**Not done / not claimed:** automatic classification as faults; injection into 13-channel inference; exact publication map reproduction.

---

## Algorithms used and why

| Step | Choice | Why |
|---|---|---|
| THG | Existing FHD product | Edge enhancement supported by 100 m TMI spacing |
| Residual blend | TMI − Gaussian | Emphasises residual anomalies without inventing structure |
| Percentile threshold | P92 default | Data-adaptive; fully logged |
| Skeletonisation | skimage or Zhang–Suen-like fallback | Traceable ridges without commercial GIS |
| Density/distance | EDT + convolution | Tractable at full Abeokuta grid size |

Directional FFT filters beyond existing magnetic ops were **not** added as a separate extraction prerequisite; THG/AS/FVD/tilt already exist as magnetic products.

---

## Generated outputs

Under `…/working/derived/lineaments/`:

- `candidate_lineaments.geojson`
- `lineament_density.tif`
- `lineament_distance.tif`
- `lineament_enhancement.tif`
- `lineament_ridge_mask.tif`
- `candidate_lineaments_preview.png`
- `lineament_extraction_qc.json`

Also: `working/candidate_lineaments.geojson` (sidecar for catalogue sampling).

Summary: `poc/abeokuta_candidate_lineament_summary.json`.

---

## Candidate lineament statistics (Abeokuta run)

| Metric | Value |
|---|---|
| n_lineaments | **72** |
| Circular mean azimuth | **80.99°** |
| Dominant bin | 90–105° |
| Length min / median / max | 500 / 1183 / 15 773 m |
| Total length | ~168 km |

Rose bins show a strong ~E–W component; NE–SW (~45°) is present but **not** dominant in this automatic extraction. Do **not** treat this as confirmation or rejection of the publication theme without geological review.

---

## Spatial coverage

Candidates inherit the TMI survey mask / grid extent in EPSG:32631. Display/map use must reproject; AOI sampling transforms WGS84 → working CRS.

---

## Quality limitations

- Candidates follow magnetic gradient ridges, not mapped faults.
- 100 m gridding limits resolvable continuity.
- Percentile / skeleton parameters are heuristics.
- Density uses a fast approximation (not exact segment clipping).
- Scientific status remains **NOT_VALIDATED**.

---

## Geological interpretation (required distinctions)

| Concept | Status here |
|---|---|
| Magnetic anomalies | Present (TMI + derivatives) |
| Candidate magnetic lineaments | **Extracted (72)** |
| Publication-guided structural trends | Contextual NE–SW note only |
| Independently validated structures | **Absent** |
| Confirmed faults / fractures | **Not labelled** |

---

## Validation status

**NOT_VALIDATED.** Additional data required: authoritative fault/fracture inventories, field structural overlays, optionally higher-resolution magnetics.

---

## Frontend / API integration

- API extract + magnetic product listing includes candidate lineament artefacts.
- Geological detail UI: “Extract candidate magnetic lineaments” + download GeoJSON + honesty copy.
- Assess overlay may sample candidate GeoJSON as analytics with `scientific_class=candidate_magnetic_lineament`, `used_in_inference=false`.
- Live 13-channel model **unchanged**.

---

## Remaining data requirements

1. Mapped faults/fractures with CRS and confidence.  
2. Peer-reviewed structural geology for the AOI.  
3. Optional higher-resolution magnetic surveys.  
4. Human geological QC of the 72 candidates before any operational use.
