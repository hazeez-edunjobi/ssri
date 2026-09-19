# Stage 2.9 — Scientific Validation & Dataset Integrity

Stage 2.9 adds a rigorous scientific validation layer around the existing SSRI
dataset, training, evaluation, and inference pipeline.

**Important:** Passing automated checks does not prove geological validity or
operational hazard accuracy.

## Motivation

SSRI must distinguish:

| Category | Examples |
|----------|----------|
| Engineering validation | tensor shapes, CRS consistency, checkpoint compatibility |
| Statistical validity | class distributions, feature shifts |
| Geospatial validity | spatial split independence, AOI overlap |
| Geological validity | labels represent actual hazards (requires human review) |
| Operational hazard validity | safe operational deployment (requires human review) |

Automated Stage 2.9 checks support the first three categories as diagnostics.
They never replace expert review.

## Architecture

```
Dataset manifest + statistics
    │
    ├── audit_dataset()           dataset integrity
    ├── audit_labels()            label contract + quality flags
    ├── audit_features()          13-channel feature audit (mmap)
    ├── validate_spatial_splits() AOI overlap + buffer
    ├── validate_dataset_independence() IDs, paths, hashes, spatial
    ├── analyze_distributions()   class + feature shift diagnostics
    └── compute_reproducibility_fingerprints()
    │
    ▼
ScientificValidationReport
    ├── scientific_validation.json
    └── scientific_validation.md
```

Package: `ssri_model.scientific`

## Dataset Audit

`audit_dataset(manifest_path, statistics_path)` returns `DatasetAuditResult`:

- sample/split counts, channel order, CRS, resolution
- duplicate IDs/paths, missing/unreadable files
- statistics presence

Read-only — datasets are never modified.

## Label Audit

`audit_labels()` checks:

- supported class IDs (0=subsidence, 1=landslide, 2=sinkhole)
- nodata, invalid classes, CRS/dimension alignment
- class absence, dominance, uniform label warnings

Warnings do not automatically mean labels are scientifically wrong.

## Feature Audit

`audit_features()` audits all 13 canonical channels using memory-mapped reads:

- min/max/mean/std, valid/nodata counts
- NaN/Inf detection, all-nodata channels, near-constant channels

No silent clipping or refitting.

## Spatial Independence

`validate_spatial_splits()` inspects WGS84 bounding boxes from sample metadata:

- overlap between train/validation/test
- optional `spatial_buffer_m` proximity violations
- minimum/maximum inter-sample distances

Different sample IDs with overlapping AOIs are flagged.

## Distribution Analysis

`analyze_distributions()` reports:

- per-class pixel counts and imbalance ratios
- per-split feature mean/std comparisons
- documented z-threshold warnings for train vs test/validation shifts

Shifts are diagnostics, not automatic failures.

## Leakage Diagnostics

`validate_dataset_independence()` and `check_feature_label_leakage()` report:

- sample ID overlap across splits
- duplicate feature/label paths and feature hashes
- suspicious feature/label path patterns
- feature/label mean association diagnostics (not proof of leakage)

## Reproducibility Fingerprints

SHA-256 fingerprints for:

- dataset manifest
- statistics file
- checkpoint (optional)
- validation configuration
- combined fingerprint

Large arrays are not hashed directly — file hashes are used.

## Validation Status Model

| Status | Meaning |
|--------|---------|
| `NOT_VALIDATED` | Default; blocking failures or insufficient evidence |
| `DATASET_AUDITED` | Automated integrity audits passed/warned |
| `SPATIALLY_VALIDATED` | Spatial independence checks passed |
| `STATISTICALLY_VALIDATED` | Reserved for future explicit statistical criteria |
| `SCIENTIFICALLY_VALIDATED` | **Human review only** via `ScientificReviewRecord` |

Automated runs never assign `SCIENTIFICALLY_VALIDATED`.

## Human Review Gate

`ScientificReviewRecord` requires reviewer, timestamp, notes, and decision
(`pending`, `accepted`, `rejected`).

Attaching an accepted review updates the report status but records expert
judgment — it does not prove geological truth by itself.

## CLI

```bash
poetry run python -m ssri_model.scientific audit \
  --manifest dataset/manifest.json \
  --statistics dataset/statistics.json

poetry run python -m ssri_model.scientific spatial --manifest dataset/manifest.json

poetry run python -m ssri_model.scientific labels --manifest dataset/manifest.json

poetry run python -m ssri_model.scientific features --manifest dataset/manifest.json

poetry run python -m ssri_model.scientific report \
  --manifest dataset/manifest.json \
  --statistics dataset/statistics.json \
  --output reports/scientific/

poetry run python -m ssri_model.scientific review \
  --report reports/scientific/scientific_validation.json \
  --reviewer "domain.expert" \
  --decision accepted \
  --notes "Reviewed against independent evidence."
```

Exit codes: `0` success, `1` warnings, `2` failure, `3` invalid configuration.

Every CLI invocation prints:

> Automated validation does not establish geological truth or operational hazard accuracy.

## Report Formats

**JSON:** status, audits, warnings, fingerprints, independence, distribution,
`scientific_validation_status`, `scientific_review_required`.

**Markdown:** sections for Engineering, Data Quality, Spatial, Statistical,
Scientific Review Requirements, and Known Limitations.

Reports are written to a separate output directory — source datasets are not modified.

## Scientific Limitations

- Bbox overlap checks are approximate, not full polygon topology review
- Feature/label association is a diagnostic, not leakage proof
- Distribution shift thresholds are engineering criteria, not geological truth
- No ground-truth fabrication or automatic hazard certification
- Large datasets use mmap/streaming but full expert review remains manual

## Related: Lagos InSAR reference (not Stage 2.9 labels)

Public Lagos InSAR deposit DOI `10.7294/19738957` was qualified (2026-09-08) as
**BENCHMARK-ONLY** external VLM / building-collapse risk reference — **not** a
drop-in `label.tif` for Stage 2.9 audits or the Evaluator. Full notes:
`docs/dataset_candidates_report.md`. Presence of that deposit does **not** set
`SCIENTIFICALLY_VALIDATED`.

## Production checkpoint gate (2026-09-08)

Automated Stage 2.9 tooling is **engineering-ready** (audits, spatial/leakage
diagnostics, fingerprints, human review attachment). It cannot run against a
production Lagos three-class dataset because **no such labelled dataset exists
in-repo**.

| Gate | Status |
|------|--------|
| Scientific tooling present | Yes |
| Labelled train/val/test dataset present | **No** |
| `SCIENTIFIC_VALIDATION` | **NOT VERIFIED** |
| Production checkpoint | **BLOCKED** (data, not code) |

## Readiness for Stage 3

Stage 2.9 provides dataset integrity auditing, spatial/leakage diagnostics,
reproducibility fingerprints, explicit validation statuses, and a human review
gate. Stage 3 can build operational deployment, monitoring, or service layers
on top of these validated artifacts without changing Stage 1–2.8 contracts.
