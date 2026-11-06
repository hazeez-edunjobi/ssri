# Review request — independent geoscientist (one page)

## What we are asking

Please review the SSRI ground-risk pipeline and its claims **before** any of its
output is treated as usable. This is a review of assumptions, evaluation
design, and honesty of the reporting — not a code review.

## What SSRI does

It takes a Stage 2.5 feature stack (13 or 16 channels) plus hazard labels
(subsidence, landslide, sinkhole) and trains a model that ranks **relative**
susceptibility. It never claims validated absolute risk. Outputs stay
`NOT_VALIDATED` and scores are withheld unless an evaluation gate is passed
**and** the query point is inside the trained region.

## Where to look

- **Limitations:** [`LIMITATIONS.md`](../LIMITATIONS.md)
- **Model card:** [`MODEL_CARD.md`](../../landslide_credibility_v3/MODEL_CARD.md)
- **Review checklist:** [`REVIEW_CHECKLIST.md`](../../landslide_credibility_v3/REVIEW_CHECKLIST.md)
- Evaluation gates and status strings: `model/src/ssri_model/release_shell/gates.py`
- How "no skill beyond slope" is decided: the slope baseline comparison in the
  release-shell evaluation.
- Real-data caveats: [`CLIENT_CSV_FINDINGS.md`](../CLIENT_CSV_FINDINGS.md) and
  [`handoff/CLIENT_QUESTIONS.md`](CLIENT_QUESTIONS.md).

## Specific questions for the reviewer

1. Is the **spatial split** (whole blocks + buffer) an acceptable way to avoid
   optimistic leakage for this kind of hazard mapping?
2. Are the **gates** and the **slope baseline** the right bar? Is
   `trained, no demonstrated skill beyond slope` a fair description when the
   model fails to beat slope?
3. Is the labelling of outputs (`local evidence only`, `NOT_VALIDATED`,
   `outside_training_region`) clear and sufficient for a non-specialist reader?
4. For the Abeokuta site (~56 km × 56 km), is the suggested block size / buffer
   reasonable (see the estimate in `RUNBOOK_FIRST_REAL_RUN.md`)?
5. What minimum data (area, labels, lineaments, dates) would you require before
   the first real model is worth training at all?

## What this is NOT

- It is not a request to certify the model, a dataset, or any number.
- It is not endorsement of any commercial, insurance, or safety use.
- All current training numbers are **SYNTHETIC** and prove mechanics only.
