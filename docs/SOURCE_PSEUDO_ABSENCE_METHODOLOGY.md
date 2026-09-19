# Source Pseudo-Absence Methodology (USGS FeatureStack v3)

**Dataset:** `data/datasets/usgs_landslide_featurestacks/v3`  
**Audit artifact:** `sampling_audit.json`

## Why pseudo-absences exist

The USGS National Landslide Inventory is **presence-only**. Confirmed field
absences are not available in the ingested catalog. Training a binary landslide
head therefore requires an explicit, documented negative class construction.

## Method (v3)

1. Select CONUS inventory positives stratified across 2° spatial blocks with a
   minimum separation of **2 km** between selected positives.
2. Generate candidates by offsetting from a random selected positive by
   **15–100 km** (land-biased; avoids ocean/DEM-void failures of uniform CONUS
   draws used in early v1 attempts).
3. Reject any candidate within **15 km of any CONUS USGS catalog point**
   (full inventory exclusion buffer — not only the selected subset).
4. Enforce **≥5 km** separation between pseudo-absences.
5. Label `landslide=0` with quality flags:
   - `pseudo_absence=true`
   - `not_field_confirmed_absence=true`
   - `full_inventory_exclusion_buffer=true`

## Audit results (selection, pre-build)

| Check | Result |
|-------|--------|
| Positives / absences | 120 / 120 (balance 0.5) |
| Absences below 15 km inventory buffer | **0** |
| Min absence→inventory distance | **15.26 km** |
| Median absence→inventory | **41.1 km** |

## Scientific caveats

- Pseudo-absences are **not** field surveys; they may include unmapped landslide
  terrain outside the inventory buffer.
- Optimizing buffers solely to raise AUC is forbidden; buffers chosen for
  contamination reduction and terrestrial coverage.
- Subsidence / liquefaction remain **missing** (not coerced to 0).
