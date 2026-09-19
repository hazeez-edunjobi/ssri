# Uncertainty methodology (SSRI)

This document describes how SSRI computes and exposes uncertainty.
These are **software estimates**, not geological guarantees.

## Components

### Monte Carlo dropout

At assessment time the model runs `mc_samples` forward passes with dropout
enabled. Per-hazard pixel means across samples form susceptibility scores.

### Empirical credible intervals

Equal-tailed empirical intervals (default 80% and 95%) are taken from the
MC sample distribution. No Gaussian assumption is made.

### Domain similarity

Channel-mean embeddings are compared to a deployment centroid via cosine
similarity, then normalized to `[0, 1]`. A default zero centroid is
conservative (low similarity) until a real training centroid is configured.

### Confidence tiers

Tiers (High / Moderate / Low / Extrapolation Warning) are **calibration
parameters** controlled by `UncertaintyConfig`. They are not scientifically
validated cutoffs.

### Attribution

Primary drivers use input-gradient magnitudes over feature channels.
This is an explanatory heuristic, not causal proof.

## API exposure rules

- Expose scores, intervals, similarity, tier, and drivers together.
- Never claim statistical certainty or field validation from these fields alone.
- Notes should retain provenance (`requested_by`, acquisition source, request id).

## Limitations

- MC dropout underestimates some forms of epistemic uncertainty.
- Domain centroid quality dominates similarity usefulness.
- Gradient attribution can be noisy on flat regions.
- Live AOI acquisition quality depends on external GEE/OpenTopo data.

## Related code

- `model/src/ssri_model/uncertainty/`
- `model/src/ssri_model/api/routes/assess.py`
- `docs/model_card.md`
