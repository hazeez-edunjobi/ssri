# Gate A — Independent dataset construction and DeepSlide evaluation

**Gate A outcome: FAIL**

A suitable independent labelled georeferenced 14-band evaluation corpus was constructed and evaluated at fixed threshold 0.5. DeepSlide did **not** meet the predeclared acceptance criteria. Production `/api/v1/assess` was not modified. This is **not** scientific validation of DeepSlide for SSRI production.

## What was built

| Item | Value |
|------|-------|
| Presence source | USGS Landslide Inventories v3 via `data/catalogs/usgs_landslide_v3/catalog.jsonl` |
| Absence source | Same 5° block feature-stack pseudo-absences (geographic block from lat/lon) |
| Imagery | Planetary Computer STAC Sentinel-2 L2A B01–B12 |
| Terrain | Copernicus DEM GLO-30 → DEM + slope (degrees) |
| Chip size | 128×128 @ 10 m |
| Packaging | `l4s-pack-v1-div-img-mean` |
| Threshold | 0.5 (fixed; not tuned on this set) |
| Chips | 24 (12 presence / 12 absence) |
| Spatial blocks | `35_-125`, `35_-80`, `35_-85` (5° cells; evaluation-only) |
| Class prevalence | 0.5 presence chips |

Independence: CONUS USGS points are outside documented L4S Asia study areas. Blocks are geographic, not random neighbour chips.

See `INVENTORY_CANDIDATES.md` for rejected alternatives.

## Predeclared gates (`acceptance.json`)

1. Chip F1 > majority-class baseline  
2. Chip F1 > terrain (mean slope > 15°) baseline  
3. Chip F1 ≥ 0.40  

## Results (chip-level, primary)

| Method | Precision | Recall | F1 | IoU | TP | FP | FN | TN |
|--------|-----------|--------|-----|-----|----|----|----|----|
| DeepSlide | 0.10 | 0.083 | **0.091** | 0.048 | 1 | 9 | 11 | 3 |
| Majority (always non-LS) | 0 | 0 | 0 | 0 | 0 | 0 | 12 | 12 |
| Slope > 15° | 0.75 | 0.25 | **0.375** | 0.231 | 3 | 1 | 9 | 11 |

Gate checks:

- Beat majority: **pass** (0.091 > 0)
- Beat slope: **fail** (0.091 < 0.375)
- Min F1 ≥ 0.40: **fail**

False-positive behaviour: 9/12 absence chips had ≥1 pixel > 0.5 (high FP rate). Recall on inventory presence chips was 1/12.

Per-block chip F1 (n=8 each): see `outputs/gate_a_eval_report.json` → `per_block_chip_model`.

Pixel metrics vs 40 m buffers are secondary and near-zero F1 (expected for tiny circular buffers vs diffuse predictions); they do not drive the verdict.

## Limitations (explicit)

- Point + 40 m buffer ≠ scar polygons  
- B10 zero-filled when absent from L2A  
- Copernicus DEM ≠ ALOS training DEM  
- Temporal window matching, not event-day guarantee  
- Pseudo-absences are inventory-gap proxies  
- Scores are uncalibrated — not risk probabilities  

## Decision

**FAIL** — dataset construction succeeded; DeepSlide failed acceptance criteria under independent CONUS spatial-block evaluation.

Do **not** authorize production integration from this gate.
