# Stage 2.5 — SSRI Training & Experiment Orchestration

## Purpose

Stage 2.5 provides the production-oriented SSRI training and experiment
orchestration layer on top of:

- Stage 2.2 dataset and dataloader contracts
- Stage 2.3 `SSRIModel` architecture

This stage delivers reproducible experiment directories, mask-aware training,
validation metrics, checkpoint/resume support, and data-leakage guards.

**Important:** Stage 2.5 proves that the training infrastructure works.
It does **not** establish that SSRI achieves useful hazard prediction
performance. Scientific evaluation requires a properly labelled,
representative dataset.

## Training Flow

```text
TrainingConfig + SSRIModel
        ↓
Pre-flight checks (manifest, splits, channel/class contracts)
        ↓
Experiment directory
        ↓
Train loader (train split only)
        ↓
SSRIModel(features) → logits
        ↓
Masked Cross Entropy(logits, labels, mask)
        ↓
Backward + optimizer (+ optional AMP / grad clip)
        ↓
Validation loader (validation split only, no_grad)
        ↓
Metrics + history + checkpoint
        ↓
Optional early stopping
```

The **test split is never loaded or evaluated** during `Trainer.fit()`.

## Configuration

`TrainingConfig` includes:

| Field | Purpose |
|-------|---------|
| `output_dir` | Root for experiment directories |
| `dataset_manifest` | Path to dataset `manifest.json` |
| `batch_size`, `num_workers`, `epochs` | Training loop |
| `learning_rate`, `weight_decay` | Optimizer |
| `optimizer` | `adam`, `adamw`, `sgd` |
| `scheduler` | `none`, `cosine`, `reduce_on_plateau` |
| `seed`, `device`, `mixed_precision` | Reproducibility / device |
| `gradient_clip_norm` | Optional clipping |
| `checkpoint_every`, `validate_every` | Checkpoint / validation cadence |
| `early_stopping_patience` | `None` disables early stopping |
| `early_stopping_monitor` | `macro_f1`, `mean_iou`, `validation_loss` |
| `loss` | Nested `LossConfig` for class weights |

Legacy `checkpoint_dir` remains supported for direct checkpoint paths.

## Loss

Primary loss: **masked cross entropy**.

Valid pixels require:

- `mask == True`
- `label != LABEL_NODATA (-1)`
- `label in {0, 1, 2}`

Use either:

```python
from ssri_model.training import masked_cross_entropy, MaskedCrossEntropyLoss
```

Zero valid pixels raise `NoValidPixelsError`.

## Metrics

Pixel-level metrics exclude invalid pixels and report:

- overall accuracy
- per-class precision / recall / F1 / IoU
- macro F1
- mean IoU
- confusion matrix

Zero-division cases return `0.0` rather than NaN.

## Experiment Directory

```text
output_dir/
  experiments/
    <experiment_id>/
      config.json
      history.json
      latest.pt
      best.pt
      logs/
        training.log
```

Existing experiment directories are not overwritten silently.

## Checkpoint Format

Checkpoints contain:

- model / optimizer / scheduler state
- epoch, seed, training history
- training and model config
- dataset manifest identity (`dataset_name`, `version`)
- best metric name and value

Resume restores model, optimizer, scheduler, epoch, and history.

## Device Selection

`resolve_device("auto"|"cpu"|"cuda")`

Mixed precision is disabled by default and only enabled when CUDA is
available and `mixed_precision=True`.

## Reproducibility

`set_seed(seed)` seeds Python, NumPy, and PyTorch. Complete bitwise GPU
determinism is not guaranteed on every backend.

## Class Imbalance

Optional explicit class weights via `LossConfig.class_weights`.

Automatic weighting requires:

```python
LossConfig(compute_class_weights_from_train=True)
```

Weights are computed from **training split labels only**.

## Test Split Isolation

`Trainer` uses train and validation loaders only. Test evaluation belongs
to a later stage.

## Safety Checks

When `dataset_manifest` is provided, training verifies:

- manifest exists
- train and validation splits are non-empty
- no overlapping sample IDs across splits
- 13 input channels in manifest
- model input channels == 13
- model classes == 3

## Example

```python
from ssri_model.architecture import create_ssri_model
from ssri_model.ml import SSRIDataset, create_dataloader
from ssri_model.training import TrainingConfig, Trainer

train_ds = SSRIDataset("./data/my-dataset", split="train")
val_ds = SSRIDataset("./data/my-dataset", split="validation")

config = TrainingConfig(
    output_dir="./outputs",
    dataset_manifest="./data/my-dataset/manifest.json",
    epochs=20,
    batch_size=4,
    device="auto",
)

trainer = Trainer(
    model=create_ssri_model(),
    config=config,
    train_loader=create_dataloader(train_ds, batch_size=4),
    validation_loader=create_dataloader(val_ds, batch_size=4),
)
result = trainer.fit()
```

## Limitations

- Single-device training only
- No experiment tracking platforms (W&B, MLflow)
- No test-set evaluation during training
- No inference serving
- Successful synthetic/offline training does not imply scientific validity

## Package Layout

```text
training/
  __init__.py
  config.py
  losses.py
  metrics.py
  trainer.py
  checkpoint.py
  history.py
  seed.py
  device.py
  experiment.py
  safety.py
  exceptions.py
  optimizer.py
  scheduler.py
```
