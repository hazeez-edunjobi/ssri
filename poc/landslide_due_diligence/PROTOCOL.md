# Landslide susceptibility due-diligence protocol

**Status:** FROZEN at Phase 1 — do not edit after SHA-256 is recorded.  
**Hazard scope:** landslide only (susceptibility, not detection).  
**Product claim under test:** “Terrain in this tile is relatively more/less prone to landslides,” not “a landslide occurred here.”

## Unit of prediction

**Primary unit: tile-level susceptibility score** in \([0,1]\).

Justification: USGS labels are inventory **points** (and FeatureStacks rasterize presence as small masks / tile labels). Pixel segmentation metrics are dominated by class prevalence (~64% positive pixels on the foundation test set) and do not match the label type. Tile scores (mean landslide-head probability over valid pixels, or mean of aggregated terrain features) are the honest match for point/pseudo-absence tile construction.

Pixel F1 is **not** a primary metric. A predict-all-positive reference at corpus prevalence is reported only for interpretation.

## Primary metrics (held-out spatial blocks)

1. Tile **ROC-AUC**
2. Tile **PR-AUC**
3. Tile **Brier score**
4. **ECE** (10 equal-width bins on predicted scores)

Secondary (reported, not used to pass/fail except where listed in acceptance): precision, recall, F1, confusion counts at the **training-block-selected** threshold; per-block ROC-AUC; prediction-prevalence histogram.

## Candidates

| ID | Method |
|----|--------|
| B0 | Majority / prevalence references: always-negative; always-positive; predict-all-positive F1 sanity at prevalence |
| B1 | Slope-only: tile score = mean slope over finite pixels; threshold chosen on **training blocks only** (Youden or F1 on train; freeze before test) |
| B2 | Logistic regression on tile aggregates of terrain channels: elevation, slope, plan_curvature, profile_curvature, twi, relative_relief, valley_depth (+ gravity/magnetics if finite and not constant). Fit on train blocks only |
| B3 | Gradient-boosted trees (sklearn `HistGradientBoostingClassifier` or equivalent) on the same features; hyperparameters tuned by nested spatial CV on train blocks only |
| B4 | Foundation U-Net (`models/ssri-foundation-v2.pt`) landslide head, intact inputs as stored |
| B5 | Foundation U-Net ablation: spectral channels (ndvi, ndwi, clay_mineral_ratio, iron_oxide_index) zeroed at inference |
| B6 | Optional: same as B2/B3 after dropping any channel that is ≥95% nodata corpus-wide |

Any additional candidate must be frozen in `phase5_freeze.json` before test blocks are opened.

## Split policy

- Spatial blocks of **5 degrees** (WGS84): block id `floor(lat/5)*5_floor(lon/5)*5`.
- Whole blocks assigned to train or test; **no tile straddling**.
- **Buffer:** discard any train–test pair of blocks whose centroids are closer than **100 km**, OR equivalently require that every test sample is ≥ **50 km** from every train sample (haversine). Exact rule applied in code must match this protocol and be logged.
- For the existing v3 corpus (2° blocks in metadata): remap samples to **5°** blocks for due-diligence splits; if remapping yields fewer than the minima below, report the largest valid configuration and do not invent samples.
- **Nested spatial CV** for any tuning: outer = held-out test blocks (untouched until Phase 6); inner = among training blocks only, leave-one-block-out or k-block CV for hyperparameters / thresholds.

### Phase 3 (existing 240) interim split

Until a scaled corpus exists, Phase 3 uses the **existing manifest train/validation/test** spatial assignment for continuity with foundation reporting, **and** also reports metrics under a 5° remapped held-out set if ≥3 test blocks exist. Phase 3 results are **diagnostic**; they cannot alone grant GO-LIMITED under the sample-size rule below.

## Minimum sample size (for GO-LIMITED)

- ≥ **1,500** tiles  
- ≥ **8** distinct 5° spatial blocks  
- ≥ **3** of those blocks held out for final test  

If free data + local compute cannot reach this without paid services or violating hard constraints, **stop scaling**, document the largest valid corpus, and Phase 9 may only return **BLOCKED** or **NO-GO** (never GO-LIMITED).

## Uncertainty

- Spatial-block bootstrap: resample **held-out blocks** with replacement (≥ **1,000** replicates).  
- Report 95% percentile CIs on every primary metric and on **ΔROC-AUC vs slope-only (B1)**.

## Acceptance criteria (mechanical; do not loosen after seeing results)

A candidate **passes** only if all of:

| # | Criterion |
|---|-----------|
| A | Lower 95% CI bound of (candidate ROC-AUC − slope-only ROC-AUC) on held-out blocks **> 0** |
| B | Candidate ROC-AUC point estimate **≥ 0.80** |
| C | ECE **≤ 0.10** on held-out blocks |
| D | Does not collapse to near-constant output: report histogram; fail if ≥95% of tile scores fall in a single 0.05-wide bin |
| E | Per-block ROC-AUC **> 0.5** in at least **75%** of held-out blocks that contain both classes |

Pass/fail printed per criterion. No post-hoc rationale changes the decision.

## Explicit non-claims

- Passing does **not** authorize production integration.  
- Passing does **not** clear `NOT_VALIDATED`.  
- Point labels do **not** support detection or scar mapping claims.  
- DeepSlide is out of scope.

## Tuning discipline

Test blocks are opened **once** per frozen candidate after `phase5_freeze.json` is written. Thresholds and hyperparameters may only be chosen using training blocks / inner CV.
