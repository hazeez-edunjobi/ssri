# Hazard taxonomy decision (PRD completion)

**Date:** 2026-09-08

## Decision

Canonical **PRD** multi-task hazards are:

1. `landslide`
2. `subsidence`
3. `liquefaction`

Implemented in `ssri_model.ingestion.schema.PrdHazard` and
`ssri_model.architecture.multitask.SSRIMultiTaskModel`.

## Legacy deviation

The pre-completion segmentation model (`SSRIModel`) uses classes:

- `subsidence` (0)
- `landslide` (1)
- `sinkhole` (2)

**Sinkhole is not renamed to liquefaction.** They are scientifically different.
Legacy checkpoints and `/api/v1/assess` hazard filters that reference `sinkhole`
remain for compatibility until a production multi-task checkpoint replaces them.

## Label missingness

Inventories that only annotate landslides set `landslide=1` and leave
`subsidence` / `liquefaction` as `null` (missing). Training uses masked BCE so
missing tasks are **not** treated as negatives.
