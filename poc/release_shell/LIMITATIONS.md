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
- Schema **v2** checkpoints require matching 16-channel inputs; mismatched assess inputs are rejected with missing channel names.
- Optional `SSRI_PREVIEW_UNEVALUATED_SCORES` (default OFF) may return preview scores for trained-but-ungated hazards; status stays **NOT_VALIDATED** and limitations are listed. Disabled / unlabelled / outside-region hazards still return null scores.
- Local block sizes (< 5°) are **local evidence only; not validated beyond this site**.
- Client Abeokuta CSV CRS, units, and Z meaning remain **UNKNOWN** until the client confirms (see `CLIENT_CSV_FINDINGS.md`).
