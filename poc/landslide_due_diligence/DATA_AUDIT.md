# DATA_AUDIT — FeatureStacks v3 + USGS catalog
Generated: 2026-11-03T19:35:13.113212+00:00
PROTOCOL.md SHA-256: `BD2A86BC5A883123B476F9CFD759026836740C60E09FD6A9ACE3BD088213DDFE`

## Plain finding — what the model could actually learn from

**Spectral channels (ndvi, ndwi, clay_mineral_ratio, iron_oxide_index) are 100% nodata (−9999) on every chip in the 240-sample corpus.** Any skill must come from terrain (± gravity/magnetics). A slope-only baseline is therefore the critical foil.

Corpus size **240** tiles across **32** five-degree blocks. PROTOCOL requires ≥1500 / ≥8 blocks / ≥3 held-out for GO-LIMITED — **not met** by v3 alone.

## Catalog

- Licence: **CC0-1.0** DOI 10.5066/P14AJF8I
- CONUS points counted: 152287
- Among dated CONUS: pre-2017=22210, post-2017=10349, frac_pre2017=0.682146257563193, undated_frac=0.7861997412779818
- Labels: presence-only landslide; subsidence/liquefaction missing

## Absence construction

- Reported method: docs/SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md — 15 km full-inventory exclusion; 15–100 km offset from positives
- Min distance to inventory (recomputed): 15.261794612573873 km
- Proposed rebuild buffer: **20.0 km**

## Leakage

- Min train–test NN (manifest split): 17.05599031090793 km
- 5° block overlap train∩test: ['30_-115', '30_-120', '35_-110', '35_-115', '35_-125', '35_-80', '35_-85', '35_-95', '40_-100', '40_-110', '40_-125', '40_-70', '40_-80']
- Pairs <0.5 km: 0

## Channel summary (mean frac nodata / frac chips all-nodata)

- `elevation`: mean_nodata=0.0249, all_nodata_chips=0.000, constant_finite=0.033
- `slope`: mean_nodata=0.0249, all_nodata_chips=0.000, constant_finite=0.033
- `plan_curvature`: mean_nodata=0.0249, all_nodata_chips=0.000, constant_finite=0.029
- `profile_curvature`: mean_nodata=0.0249, all_nodata_chips=0.000, constant_finite=0.033
- `twi`: mean_nodata=0.0620, all_nodata_chips=0.029, constant_finite=0.000
- `relative_relief`: mean_nodata=0.0249, all_nodata_chips=0.000, constant_finite=0.033
- `valley_depth`: mean_nodata=0.0249, all_nodata_chips=0.000, constant_finite=0.033
- `ndvi`: mean_nodata=1.0000, all_nodata_chips=1.000, constant_finite=0.000
- `ndwi`: mean_nodata=1.0000, all_nodata_chips=1.000, constant_finite=0.000
- `clay_mineral_ratio`: mean_nodata=1.0000, all_nodata_chips=1.000, constant_finite=0.000
- `iron_oxide_index`: mean_nodata=1.0000, all_nodata_chips=1.000, constant_finite=0.000
- `gravity`: mean_nodata=0.0001, all_nodata_chips=0.000, constant_finite=0.196
- `magnetics`: mean_nodata=0.0001, all_nodata_chips=0.000, constant_finite=0.183
