# Stage 2.5 dataset specification (release shell)

Channel schemas are **versioned**. Checkpoints store `channel_schema_version` and ordered `channel_names`. Assess rejects inputs that do not match and names missing channels.

## Schema v1 (default — unchanged)

- File: `feature_stack.npy`
- Shape: `(13, H, W)` float32
- Channel order (**exact**):

| Index | Name |
|------:|------|
| 0 | elevation |
| 1 | slope |
| 2 | plan_curvature |
| 3 | profile_curvature |
| 4 | twi |
| 5 | relative_relief |
| 6 | valley_depth |
| 7 | ndvi |
| 8 | ndwi |
| 9 | clay_mineral_ratio |
| 10 | iron_oxide_index |
| 11 | gravity |
| 12 | magnetics |

## Schema v2 (additive)

Shape `(16, H, W)`. v1 channels **0–12** unchanged, then:

| Index | Name | Notes |
|------:|------|-------|
| 13 | overburden_thickness | metres. If the client supplies **depth to bedrock**, declare that name separately — never silently relabel as thickness. |
| 14 | lineament_density | m/m² in a square window (default 500 m); derived from GeoJSON lines or supplied as a raster |
| 15 | lineament_distance | metres to nearest lineament |

Declare `"channel_schema_version": "v2"` in `manifest.json`.

- Nodata sentinel: `-9999` (`FEATURE_NODATA`). Do **not** fill unused channels with -9999 for every pixel (validator FAILs ~100% nodata channels). Gaps in point-grid CSVs are reported; SSRI does **not** interpolate.

## Labels

- File: `label.tif` (GeoTIFF, georeferenced)
- Integer classes: **subsidence=0**, **landslide=1**, **sinkhole=2**
- Nodata / ignore: **-1**
- CRS required (e.g. EPSG:4326); geotransform required

## Metadata (`metadata.json`)

Required for spatial splitting:

- `centroid_lat`, `centroid_lon` (or inferable from georeferenced label)
- Prefer: `crs`, `imagery_date`, `label_date`, `block`

SYNTHETIC demos must set `"synthetic": true` and include `SYNTHETIC` in the sample id.

## Layout

```text
{dataset}/
  manifest.json
  statistics.json
  train/{id}/feature_stack.npy
  train/{id}/label.tif
  train/{id}/metadata.json
  validation/...
  test/...   # held-out blocks after release-shell spatial split
```

## Dates

Static terrain/environment features only for susceptibility ranking. Event dates must not be used as model inputs. Mismatched imagery vs label dates produce a **WARN** only.

## Splits (release shell)

Whole blocks with configurable buffer (default **50 km**). Default block size remains **5°**. For local sites set `SSRI_RELEASE_SHELL_BLOCK_SIZE_KM` (e.g. 5–20). Random 70/15/15 is **not** used when `SSRI_RELEASE_SHELL=true`. When block size is below 5°, every evaluation report and assess response must include **local evidence only; not validated beyond this site**.

## Owner minimums (production defaults)

| Requirement | Default |
|-------------|---------|
| Tiles | ≥ 300 |
| Separate blocks (at the chosen block size) | ≥ 8 |
| Held-out blocks | ≥ 3 |

Demo/SYNTHETIC runs may lower these via `SSRI_RELEASE_SHELL_MIN_*` env vars. Empty (all-sentinel) channels cause **FAIL**.

## Point-grid CSV layers

Headerless or headed X/Y/value CSVs are accepted with a **declared CRS** (EPSG or WKT). A single layer validates as **FEATURE_LAYER_ONLY** and cannot train until the full schema channels and labels are present.

## Labels

Upload a label inventory (CSV/GeoJSON with hazard + optional date). Training refuses without labels. The validator reports per-hazard counts and **insufficient labelled data** below minimums.
