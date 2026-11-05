# Claims / wording audit (copy + API + UX)

Required framing everywhere susceptibility is shown:

> relative landslide susceptibility index derived from terrain/environment; evaluated only on CONUS held-out blocks; a ranking score, not a probability and not a risk estimate; not independently reviewed

## Status badge text (by credibility level)

| Level | Badge |
|-------|-------|
| L1 | `L1 — reproducible baselines on leakage-free blocks` |
| L2 | `L2 — candidate beats slope-only (Tier A)` |
| L3 | `L3 — L2 + external transfer + complete claims audit` |
| L4 | `L4 — independent human review` (agent cannot claim) |
| L5 | `L5 — prospective validation on post-freeze events` (agent cannot claim) |

v3 reached: **L1** with decision **NO-GAIN** → ship slope-only index. Badge:

`L1 — reproducible baselines on leakage-free blocks (NO-GAIN: slope-only product)`

## Instances to replace (non-exhaustive scan of product surfaces)

| Location (typical) | Current implication | Replacement |
|--------------------|---------------------|-------------|
| Marketing “risk” / “hazard probability” | Absolute risk | “relative landslide susceptibility ranking (CONUS evidence only)” |
| Assess UI “probability” labels | Calibrated probability | “ranking score (not a probability)” |
| “Validated model” / “production-ready” | Scientific validation | “research-ready, NOT_VALIDATED; not independently reviewed” |
| Sinkhole/subsidence numeric panels | Implies available classes | “not available” with no score |
| Demo “detection” language | Event detection | “relative susceptibility index from static terrain” |
| ECE/calibration UX as gate | Real-world probability | Remove as product gate; informational only if shown |
| Live Render “checkpoint verified” | Identity known | Mark **UNKNOWN** unless operator verifies hash |

## Live endpoint today (VERIFIED from repo; live Render identity UNKNOWN)

- Route: `POST /api/v1/assess` (Stage 2.5 `SSRIModel`, 13-channel stack).
- Returns multi-class raster/scores for subsidence / landslide / sinkhole via current checkpoint path — **not** the v3 slope-only index.
- Softmax/sigmoid mismatch still present in assess/MC paths (see SOFTMAX patch).
- DeepSlide unwired. v3 models are PoC only under `poc/landslide_credibility_v3/`.
- Live Render checkpoint SHA: **UNKNOWN** (not verified in this cycle).
