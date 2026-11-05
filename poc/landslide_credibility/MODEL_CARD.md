# Model card — CONUS landslide susceptibility (credibility cycle)

**Best multivariate freeze:** `corpus/models/NEAR_hgb.pkl` (HistGradientBoosting).  
**Honest foil:** slope-only (often stronger or tied under CIs).  
**Decision:** NO-GO (Tier A failed). **Not for production.**

## Intended use (research only)

Rank CONUS locations by **relative landslide susceptibility** from static terrain.

## Non-claims

Not detection; not real-world probability; not risk; not validated outside CONUS; not for sinkhole/subsidence.

## Limitations

- Inventory point labels + pseudo-absences  
- Mapping-effort bias  
- Slope dominates; multivariate gain not CI-significant  
- High ECE / sparse validation positives  
- No successful external transfer this cycle  

## Data biases

See `DATA_SHEET.md`.
