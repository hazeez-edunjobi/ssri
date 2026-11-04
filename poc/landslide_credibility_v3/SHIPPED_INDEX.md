# Shipped susceptibility index (v3 NO-GAIN)

**ID:** `ssri_landslide_slope_only_v3`  
**Decision:** NO-GAIN → multivariate candidates discarded.

## Definition

1. Extract DEM slope at the query point (Copernicus GLO-30 window; same feature code as corpus).
2. Convert slope to a ranking score = empirical CDF of slopes in `corpus/lobo_near.jsonl` (training pool for LOBO NEAR).
3. Optional binary display threshold = `outputs/phase3_freeze.json` → `NEAR.thr_slope` (≈ 0.40).

## What the endpoint should say

- relative landslide susceptibility index derived from terrain/environment  
- evaluated only on CONUS held-out blocks  
- ranking score, not a probability and not a risk estimate  
- not independently reviewed  
- badge: `L1 — reproducible baselines on leakage-free blocks (NO-GAIN: slope-only product)`

## What it never claims

Risk, calibrated probability, detection, validated geological truth, sinkhole/subsidence scores, non-CONUS validity, L4/L5.

## Frozen hashes

See `outputs/phase3_freeze.json` and `corpus/manifest.json`. Multivariate `*.pkl` under `corpus/models/` are research-only.
