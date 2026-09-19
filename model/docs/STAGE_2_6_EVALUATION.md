# Stage 2.6 — SSRI Test-Set Evaluation

## Purpose

Stage 2.6 implements a dedicated, immutable test-set evaluation layer for SSRI.

It answers:

> How does a specific trained SSRI checkpoint perform on the completely
> held-out test dataset?

This stage evaluates a supplied checkpoint. It does **not** train the model,
select checkpoints, tune thresholds, or establish scientific validity.

## Evaluation Architecture

```text
EvaluationConfig
      ↓
validate test split + leakage checks
      ↓
load Stage 2.5 checkpoint → SSRIModel (eval mode)
      ↓
SSRIDataset(split="test") + create_dataloader()
      ↓
for batch in test_loader (torch.no_grad):
      logits = model(features)
      update metrics + optional artifacts
      ↓
evaluation.json + evaluation.md + confusion_matrix.json
```

## Test-Only Contract

The evaluator consumes **only** the `test` split.

It never loads or evaluates:

- `train`
- `validation`

Pre-flight checks reject overlapping sample IDs between test and other splits.

## Checkpoint Selection

The checkpoint path is supplied explicitly. Model selection using validation
metrics must occur during Stage 2.5 training — not during evaluation.

Checkpoint compatibility validates:

- 13 input channels
- 3 output classes
- dataset name/version (when recorded in checkpoint)

## Metrics

Mask-aware pixel metrics exclude:

- `mask == False`
- `label == LABEL_NODATA (-1)`

Reported metrics:

- overall accuracy
- macro precision / recall / F1
- mean IoU
- per-class precision, recall, F1, IoU
- 3×3 confusion matrix (rows = actual, columns = predicted)

Zero division returns `0.0` — never NaN.

## Prediction Outputs

Optional artifacts per sample:

| File | Content |
|------|---------|
| `prediction.tif` | Class IDs 0–2, nodata `-1` |
| `confidence.tif` | Max softmax probability |
| `probabilities.tif` | 3-band softmax probabilities |

GeoTIFF outputs preserve CRS, affine transform, width, and height from the
source label grid.

## Confidence Interpretation

Model confidence is the maximum softmax probability. It has **not** been
calibrated unless a separate calibration procedure is performed.

## Report Format

Written to the evaluation output directory:

- `evaluation.json` — structured result
- `evaluation.md` — human-readable report
- `confusion_matrix.json` — labelled matrix
- `sample_results.json` — per-sample metrics

## Reproducibility

Reports record:

- checkpoint path, epoch, best metric
- dataset name and version
- model configuration
- channel order and count
- device, timestamps, duration
- package version

## Scientific Validity

`scientific_validation_status` distinguishes engineering validation from
scientific validation:

| Status | Meaning |
|--------|---------|
| `NOT_VALIDATED` | Synthetic/offline fixtures (default) |
| `LIMITED` | Real but small/non-representative data |
| `VALIDATED` | Reserved for future representative validation |

Successful synthetic evaluation does **not** establish real-world hazard
prediction capability.

## Public API

```python
from ssri_model.evaluation import EvaluationConfig, Evaluator, evaluate_checkpoint

config = EvaluationConfig(
    checkpoint_path="experiments/run-001/best.pt",
    dataset_manifest="datasets/demo/manifest.json",
    output_dir="evaluation/run-001",
    device="auto",
)
result = Evaluator(config).evaluate()
```

## Limitations

- No training or weight updates during evaluation
- No test-set normalization refitting
- No threshold tuning on test labels
- Single-device inference only
- Does not prove geological or operational hazard prediction accuracy

## Package Layout

```text
evaluation/
  __init__.py
  config.py
  evaluator.py
  metrics.py
  predictions.py
  report.py
  safety.py
  exceptions.py
```
