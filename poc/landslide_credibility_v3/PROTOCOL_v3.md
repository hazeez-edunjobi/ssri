# Landslide susceptibility credibility protocol v3

**Status:** FROZEN at Phase 1 — do not edit after SHA-256 is recorded.  
**Does not modify:** PROTOCOL.md (v1) or PROTOCOL_v2.md.

## Changes from v2 (written AFTER seeing v2 NO-GO / L1 results)

| Change | Reason |
|--------|--------|
| Primary eval = leave-one-block-out (LOBO) over all populated 5° blocks | v2 single holdout (5 blocks, n_test=309) underpowered; ΔAUC CIs crossed 0 |
| v2 test blocks labelled **exploratory, second look** — cannot count toward acceptance | Those blocks are spent |
| Sealed fresh holdout blocks listed below | Need unused cells for Tier B confirmation |
| Pre-scoring power analysis; if MDD ΔAUC > 0.08, null result = INCONCLUSIVE not NO-GO | Avoid over-claiming “no gain” when underpowered |
| ECE/Brier demoted to INFORMATIONAL (not gates) | Sampling fixes prevalence; scores are ranking scores |
| Three absence schemes: NEAR, FAR, SLOPE-MATCHED; SLOPE-MATCHED required for “beyond slope” | v2 NEAR may reward slope separation; slope-matched tests residual skill |
| Acceptance → GO-LIMITED / RESEARCH-CREDIBLE / NO-GAIN / INCONCLUSIVE | Distinguish power failure from true no-gain |
| Pre-registered environment layers one-at-a-time on LOBO | Registered before scoring; keep only if ΔAUC CI > 0 |
| U-Net dropped from scope | v2 showed no earned complexity |
| ≥5 seeds for stochastic models | Stronger seed reporting |

## Claim

Relative landslide **susceptibility** from static terrain (± registered environment layers).  
Not detection. Not real-world probability. Not validated risk. CONUS → CONUS only.

## Evaluation design

### Primary: LOBO spatial CV

- Over **all** populated 5° blocks in the v3 working set (v2’s 20 blocks plus any newly added non-sealed blocks used for LOBO).  
- For each held-out block: train on remaining blocks (with nested tuning inside training folds only); apply **50 km** buffer dropping training samples within 50 km of any held-out sample.  
- Never tune using the held-out block of that fold.  
- Aggregate metrics across folds; block-bootstrap CIs by resampling held-out blocks (≥1000).

### Spent v2 test blocks (exploratory only)

`35_-125`, `40_-120`, `40_-125`, `45_-120`, `45_-75`  
Results on these may be reported as **“exploratory, second look”** and **cannot** count toward Tier A/B.

### Sealed fresh holdout (assigned now — do not open until phase3_freeze.json)

Attempt to populate from USGS inventory + DEM (free sources only):

1. `40_-115`  
2. `30_-105`  
3. `35_-105`  
4. `45_-115`  
5. `55_-150` (Alaska, if catalog points exist)  
6. `20_-155` (Hawaii, if catalog points exist)  
7. `15_-65` (Puerto Rico / Caribbean CONUS-adjacent inventory, if points exist)

**Minimum for Tier B path:** ≥3 sealed blocks with both classes and ≥150 sealed samples total after buffers.  
If unreachable: report exact shortfall; rely on LOBO only; Tier B cannot pass; decision may be RESEARCH-CREDIBLE / NO-GAIN / INCONCLUSIVE only.

## Power analysis (before scoring)

Simulate minimum detectable ΔAUC (MDD) vs slope-only for LOBO and for sealed holdout (assumptions recorded in `outputs/phase1_power.json`).  
If MDD > **0.08**, any “no difference” result is **INCONCLUSIVE**, not NO-GAIN.

## Features

Same terrain set as v2 (Copernicus DEM GLO-30): elevation, slope, aspect_sin/cos, plan/profile curvature, twi, relative_relief_1km, valley_depth, tpi.  
Dropped: spectral, gravity, magnetics, event/date features.  
Environment layers (pre-registered, one-at-a-time): land cover (NLCD or ESA WorldCover), WorldClim/CHIRPS precip climatology, USGS/GLiM lithology, soils. Keep only if LOBO ΔAUC vs previous best has lower CI bound > 0.

## Absence schemes

| Scheme | Rule | Role |
|--------|------|------|
| NEAR | 5–20 km from presence, in inventory footprint | **Headline / Tier A primary** |
| FAR | ≥20 km, in footprint | Secondary report |
| SLOPE-MATCHED | Absences matched to presence slope distribution (terrain bins) | **Beyond-slope criterion** |

## Candidates

B0 majority; B1 slope-only; B2 logreg; B3 HGB; then B2/B3 + layers L1→L4 as above. U-Net out of scope.

## Tuning

Nested spatial CV inside training folds only. ≥5 seeds: 42,43,44,45,46. Thresholds on train only. Calibration (isotonic) on inner-val only — scores still described as **ranking scores**.

## Metrics

Primary: ROC-AUC, PR-AUC, ΔAUC vs slope with block-bootstrap 95% CIs, per-block AUC.  
Informational: Brier, ECE, reliability, histograms, confusion at train threshold.

## Acceptance (mechanical)

**Tier A (better than slope):** On LOBO under NEAR, lower 95% CI of ΔAUC vs slope **> 0**; **and** SLOPE-MATCHED ΔAUC point estimate **> 0**; **and** AUC > 0.5 in ≥75% of held-out blocks (NEAR LOBO).

**Tier B:** Tier A **and** sealed fresh holdout ΔAUC point > 0 and AUC ≥ 0.75.

| Outcome | Rule |
|---------|------|
| GO-LIMITED | Tier B passed |
| RESEARCH-CREDIBLE | Tier A only |
| NO-GAIN | Tier A failed and MDD ≤ 0.08 → slope-only is the shipped product |
| INCONCLUSIVE | Tier A failed and MDD > 0.08 |
| BLOCKED | Precise data/compat stop |

## Plausibility

PD of score on slope non-decreasing over 10th–90th percentile train slope; report violations per candidate.

## Explicit non-claims

No production integration. No `NOT_VALIDATED` clearance. No detection. No non-CONUS claim without local validation.
