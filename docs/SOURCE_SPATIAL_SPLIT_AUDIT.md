# Source Spatial Split Audit (USGS FeatureStack v3)

**Strategy:** Hold out entire **2° × 2°** geographic blocks (seed=7).  
**Artifact:** `data/datasets/usgs_landslide_featurestacks/v3/sampling_audit.json`

## Design goal

Avoid random pixel/sample splits that place neighbouring landslides into both
train and test (spatial leakage).

## Results (selection of 240 points)

| Split | Samples | Positives | Negatives |
|-------|---------|-----------|-----------|
| train | 179 | 85 | 94 |
| validation | 33 | 17 | 16 |
| test | 28 | 18 | 10 |

| Check | Result |
|-------|--------|
| Spatial blocks | **104** |
| Blocks appearing in >1 split | **0** (none) |
| Min train↔test nearest neighbour | **17.1 km** |
| Median train↔test NN | **65.8 km** |

## Geographic extent (WGS84)

- All: lat 31.17–48.45, lon −124.46–−67.72 (CONUS)
- Train / val / test each span coast-to-interior CONUS; extents recorded in audit JSON

## Limitations

- Block size (2°) is coarse; residual long-range autocorrelation may remain.
- Test has fewer negatives than positives (10 vs 18) — class balance imperfect
  by block assignment; documented, not rebalanced by leaking blocks.
- Final usable counts after FeatureStack build may be lower if extractions fail.
