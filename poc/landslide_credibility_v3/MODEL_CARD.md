# Model card — SSRI landslide susceptibility v3 (NO-GAIN product)

## Shipped index

**Name:** `ssri_landslide_slope_only_v3`  
**Definition:** For a query location, compute DEM slope (same feature pipeline as v2/v3 corpus). Map slope to a ranking score via the empirical CDF of slopes on the LOBO NEAR training pool (`lobo_near.jsonl`). Threshold for binary display (if any) = median of per-fold train-selected Youden thresholds recorded in `outputs/phase3_freeze.json` → `NEAR.thr_slope` ≈ **0.40**.

**Frozen artifacts**

| Artifact | Path | Role |
|----------|------|------|
| Protocol | `PROTOCOL_v3.md` | SHA-256 `70FE823F…` |
| Corpus | `corpus/lobo_near.jsonl` + `corpus/manifest.json` | Slope CDF reference |
| Freeze | `outputs/phase3_freeze.json` | Thresholds + model hashes (multivariate not shipped) |

Multivariate logreg/HGB pickle files under `corpus/models/` are **research artifacts only** — they failed Tier A and must not be promoted.

## Intended use

Relative ranking of landslide susceptibility from **static terrain** for CONUS research exploration.

## Out of scope

Detection, event probability, risk, sinkhole, subsidence, Alaska/Hawaii/PR product claims, production geological advice.

## Training / evaluation data

USGS landslide inventory points + Copernicus DEM terrain features; NEAR / FAR / SLOPE-MATCHED pseudo-absences. See `DATA_SHEET.md`.

## Metrics (headline)

LOBO NEAR, slope-only: ROC-AUC **0.891** (block-bootstrap 95% CI ≈ [0.738, 0.933]).  
ΔAUC of logreg/HGB vs slope: negative point estimates; CI lower ≤ 0 → Tier A **FAIL** → **NO-GAIN**.

## Ethical / bias notes

Inventory mapping effort bias; undated events; pseudo-absences; CONUS-only evidence.

## Credibility

**L1** — reproducible baselines on leakage-free blocks. L4/L5 require human review / prospective validation (agent cannot claim).
