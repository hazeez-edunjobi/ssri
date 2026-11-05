# Landslide susceptibility credibility protocol v2

**Status:** FROZEN at Phase 1 — do not edit after SHA-256 is recorded.  
**Supersedes for this cycle:** acceptance/split/feature rules below.  
**Does not modify:** `poc/landslide_due_diligence/PROTOCOL.md` (v1).

## Changes from v1 (justified by v1 audit)

| Change | Reason (v1 finding) |
|--------|---------------------|
| Point-level unit with fixed DEM neighbourhood features | Point labels ≠ scar pixels; pixel F1 misleading |
| Assign splits by **5° cell**, never by sample; assert disjointness in tests | v1 remapped 2°→5° left train∩test block overlap |
| Enforce ≥50 km train–test sample buffer; log drops | v1 min NN ~17 km insufficient vs protocol intent |
| Terrain-first features from Copernicus DEM only; spectral **dropped** | ndvi/ndwi/clay/iron 100% nodata corpus-wide |
| Thin presences ≥1 km; cap single inventory source share per block | Pseudo-replication / storm clusters in USGS catalog |
| Absences inside mapped-inventory footprints; NEAR + FAR schemes | Unmapped-region contamination risk |
| Primary model class: logreg / GBM; U-Net **optional only** | U-Net did not beat logreg; complexity unjustified |
| Tier A / Tier B acceptance (not single 0.80+CI bundle as sole path) | Allow RESEARCH-CREDIBLE if only slope-beating CI holds |
| Static predictors only (no event/imagery date features) | Temporal mismatch / detection leakage |
| Pre-register Phase 5 environment layers below | Avoid post-hoc layer shopping on same test blocks |

## Claim under test

Relative **landslide susceptibility** from static terrain (± optional static environment layers).  
Not detection. Not calibrated real-world probability. Not validated risk. CONUS evidence → CONUS only.

## Unit of prediction

**Point-level** susceptibility score in \([0,1]\).

Features extracted from a fixed DEM neighbourhood around each point:

| Window | Purpose |
|--------|---------|
| 3×3 @ 30 m (~90 m) | Local slope, aspect, curvatures |
| 1 km radius / 33×33 @ 30 m | Relative relief, TPI, valley-depth proxy, TWI neighbourhood |

Positional error in inventory points is absorbed by neighbourhood aggregation (mean/p90), not by inventing scar polygons.

## Spatial split

1. Block id = `floor(lat/5)*5_floor(lon/5)*5` (WGS84).  
2. Entire 5° cell → exactly one of `{train, validation, test}`.  
3. ≥8 populated cells; ≥3 cells held out as **test**.  
4. After assignment, drop any sample within **50 km** of any sample in a different role that would violate train↔test separation (specifically: drop train/val samples within 50 km of any test sample, and vice versa — implement as: remove samples from train/val within 50 km of test; if a test sample is within 50 km of remaining train, drop that test sample). Log counts.  
5. Assert in automated tests: no shared block ids across roles; min train–test NN ≥ 50 km.

## Sample size

≥ **1,500** points (presence + absence) after thinning and buffers.  
If unreachable from free sources, report largest valid size and stop (BLOCKED).

## Pseudo-replication control

1. Thin presence points to minimum **1 km** spacing (greedy).  
2. Cap any single catalog `source` / inventory id at **≤25%** of presences within each 5° block (subsample randomly with seed 42).  
3. Report n before/after each step.

## Absences

- Sample only inside the **buffered convex footprint** of mapped inventory points per 5° block (or CONUS hull of selected block inventories), so absences are in mapped regions.  
- Exclusion buffer from every known USGS CONUS landslide point.  
- **NEAR (PRIMARY):** uniform in footprint, distance to nearest presence in **[5, 20] km**.  
- **FAR (SECONDARY):** distance **≥ 20 km** from nearest presence, still inside footprint.  
- Target roughly balanced prevalence overall; report prevalence per block.  
- Absences are **not** field-confirmed.

## Features (static, Copernicus DEM GLO-30 via Planetary Computer STAC)

Computed from DEM; void/nodata pixels excluded from neighbourhood stats; if >40% void in window → sample **dropped** (logged).

1. elevation (m)  
2. slope (degrees)  
3. aspect_sin, aspect_cos  
4. plan_curvature  
5. profile_curvature  
6. twi (approx from slope + upstream proxy / local relief)  
7. relative_relief_1km  
8. valley_depth (elev − local min in 1 km)  
9. tpi (elev − mean elev in 1 km)

**Dropped explicitly:** ndvi, ndwi, clay_mineral_ratio, iron_oxide_index, gravity, magnetics, Sentinel bands, any event-dated feature.

DEM voids: nodata ignored in aggregations; sample dropped if insufficient valid cells.

## Candidates

| ID | Method | Role |
|----|--------|------|
| B0 | Majority / constant references | Sanity |
| B1 | Slope-only; threshold on **train** only | Required baseline |
| B2 | Logistic regression on feature vector | Primary |
| B3 | HistGradientBoostingClassifier | Primary |
| B4 | U-Net on DEM-derived chips | **Optional**; not primary; only if chips rebuilt under this protocol |

## Tuning / calibration

- Nested spatial CV on **train blocks only** (≥3 seeds: 42, 43, 44).  
- Threshold / hyperparameters chosen on train inner folds.  
- Platt or isotonic calibration fit on **validation blocks only**.  
- Test blocks opened **once** per frozen candidate after `phase3_freeze.json`.

## Metrics (held-out test)

ROC-AUC, PR-AUC, Brier, ECE (post-calibration), reliability bin data, per-block AUC + n, confusion at train-selected threshold.  
Spatial-block bootstrap ≥1000 resamples; 95% CIs on metrics and ΔAUC vs B1.

## Acceptance tiers

**Tier A — better than trivial terrain rule**  
1. Lower 95% CI of (candidate ROC-AUC − slope ROC-AUC) **> 0**  
2. Point ROC-AUC **> 0.5** in ≥ **75%** of held-out blocks with both classes  

**Tier B — original bar**  
Tier A **and** ROC-AUC ≥ **0.80** **and** ECE ≤ **0.10** **and** not near-constant (≥95% scores in one 0.05-wide bin → fail)

Mechanical PASS/FAIL only.

## Plausibility

Partial dependence of predicted susceptibility on slope must be **non-decreasing** over the central 10th–90th percentile slope range on train; report violations.

## Phase 5 environment layers (pre-registered)

Add one at a time **only if** Phase 4 reaches Tier A **or** best terrain AUC < 0.80. Same test blocks allowed because registered **before** Phase 4:

1. ESA WorldCover (or NLCD if WorldCover unavailable free) — land cover  
2. WorldClim long-term mean precipitation  
3. GLiM / USGS lithology (free public extract)  
4. Soils (USDA / SoilGrids free)

Keep a layer only if ΔAUC vs previous best has lower CI bound > 0.

## Phase 6 external transfer (report-only)

Frozen best candidate on NASA Global Landslide Catalog (or documented substitute if unavailable), same absence logic, no retune. Not part of Tier A/B.

## Explicit non-claims

Passing Tier A/B does not authorize production integration, does not clear `NOT_VALIDATED`, does not support detection or non-CONUS deployment without local validation.
