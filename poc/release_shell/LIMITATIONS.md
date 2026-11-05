# Known limitations (release shell)

- Status is always **NOT_VALIDATED**.
- Scores are **relative susceptibility rankings**, not probabilities, not risk, not detection.
- Must never be used for insurance, engineering, safety, or emergency decisions.
- Geography is limited to the uploaded training extent/blocks; outside → `outside_training_region`.
- Hazards below minimum labelled tiles/blocks are **DISABLED** → assess returns `not_available` with score null.
- Gate `evaluated` requires the skill gate on **≥2 of 3** seeds; otherwise `trained, unconfirmed across seeds` or `trained, no demonstrated skill beyond slope`.
- Slope-only baselines often match or beat multivariate models (see credibility v3 NO-GAIN research).
- **SYNTHETIC** templates are fabricated; never present their metrics as real.
- FeatureStacks v3 as-shipped has four all-sentinel spectral channels → validation **FAIL** / hazards disabled until repaired.
- DeepSlide remains an isolated research engine — **not** wired into assess.
- Default product behaviour with `SSRI_RELEASE_SHELL` unset/false is unchanged (legacy assess requires checkpoint).
