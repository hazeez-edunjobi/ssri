# Model card — best diagnostic candidate (not production)

**Candidate:** `B2_logreg` — L2 logistic regression on tile aggregates of terrain (+ gravity/magnetics).  
**Status:** Diagnostic only on FeatureStacks v3 manifest test (n=28). **Did not pass PROTOCOL acceptance.**  
**Not authorized for production.** Remain `NOT_VALIDATED`.

## Intended use (if ever promoted after a passing protocol run)

- Landslide **susceptibility ranking** of tiles/AOIs (“more/less prone relative to training distribution”).
- Research and internal planning support with explicit uncertainty.

## Out of scope / non-claims

- Not event **detection** or scar mapping.
- Not calibrated probability of failure.
- Not insurance pricing, legal compliance, or life-safety decisions.
- Not subsidence or sinkhole.
- Not DeepSlide.

## Training / eval data (this cycle)

- USGS FeatureStacks v3, 240 tiles, presence + pseudo-absence.
- Spectral channels unusable (100% −9999).
- Manifest spatial split; remapped 5° blocks **overlap** train/test — not protocol-clean.

## Known limitations

- Small test n; ΔAUC vs slope not significant by block bootstrap.
- ECE > 0.10.
- Labels are inventory points / synthetic absences.
- No Stage 2.5 three-class checkpoint exists for assess.

## Metrics (manifest test, VERIFIED in phase3_baselines.json)

| Metric | Value |
|--------|-------|
| ROC-AUC | 0.800 |
| PR-AUC | 0.857 |
| Brier | 0.185 |
| ECE | 0.189 |
| ΔAUC vs slope (point) | +0.106 |
| ΔAUC 95% CI | [−0.067, 0.309] — includes 0 → **FAIL A** |
