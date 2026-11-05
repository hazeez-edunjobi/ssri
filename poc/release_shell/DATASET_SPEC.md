# Stage 2.5 dataset specification (release shell)

## Feature stack

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

- Nodata sentinel: `-9999` (`FEATURE_NODATA`). Do **not** fill unused channels with -9999 for every pixel (validator FAILs ~100% nodata channels).

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

Whole **5° blocks** with configurable buffer (default 50 km). Random 70/15/15 is **not** used when `SSRI_RELEASE_SHELL=true`.

## Owner minimums (production defaults)

| Requirement | Default |
|-------------|---------|
| Tiles | ≥ 300 |
| Separate 5° blocks | ≥ 8 |
| Held-out blocks | ≥ 3 |

Demo/SYNTHETIC runs may lower these via `SSRI_RELEASE_SHELL_MIN_*` env vars. Empty (all-sentinel) channels cause **FAIL**.
