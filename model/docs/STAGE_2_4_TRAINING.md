# Stage 2.4 — SSRI Training & Optimization

## Purpose

Stage 2.4 implements a complete, reproducible, mask-aware training and validation
system for the SSRI geohazard segmentation model.

This stage proves that the model **can train correctly** with the Stage 2.2 data
contract and Stage 2.3 architecture. It does **not** prove real-world hazard
prediction accuracy, geological validity, or production readiness.

## Training Architecture

```text
DataLoader
    ↓
features + labels + mask
    ↓
SSRIModel(features)
    ↓
logits (B, 3, H, W)
    ↓
Masked Cross Entropy(logits, labels, mask)
    ↓
Backward
    ↓
Optimizer (+ optional grad clip)
    ↓
Updated Model
    ↓
Validation (no_grad)
    ↓
Metrics + Checkpoint / Early Stopping
```

## Public API

```python
from ssri_model.architecture import create_ssri_model
from ssri_model.training import (
    TrainingConfig,
    Trainer,
    masked_cross_entropy,
    create_optimizer,
    create_scheduler,
    resolve_device,
    set_global_seed,
)

model = create_ssri_model()
config = TrainingConfig(epochs=20, batch_size=4, learning_rate=1e-3)
trainer = Trainer(model=model, config=config)
result = trainer.fit(train_loader, validation_loader)
```

## Loss Function

Primary loss: **masked cross entropy**.

```python
loss = masked_cross_entropy(logits, labels, mask, class_weights=weights)
```

A pixel contributes to the loss only when:

- `mask` is `True` (valid feature pixel from Stage 2.2)
- `label` is in `{0, 1, 2}` (subsidence, landslide, sinkhole)
- `label != LABEL_NODATA` (-1)

If no valid pixels remain in a batch, `NoValidPixelsError` is raised.

Invalid label values are replaced in a **cloned** target tensor for PyTorch
cross-entropy compatibility, but those pixels are excluded from the final mean.

## Mask Handling

| Tensor | Passed to model? | Used in loss/metrics? |
|--------|------------------|------------------------|
| `features` | Yes | No |
| `label` | No | Yes |
| `mask` | No | Yes |

The model never receives the mask. Nodata feature pixels and label nodata values
do not contribute to gradients or metrics.

## Class Weighting

Optional class weights can be supplied via `TrainingConfig.class_weights`:

```python
TrainingConfig(class_weights=(1.0, 2.0, 1.5))
```

Or computed from **training labels only**:

```python
from ssri_model.training import compute_class_weights

weights = compute_class_weights(train_dataset)
trainer = Trainer(model=model, config=config, class_weights=weights)
```

Weight formula (inverse frequency):

```text
weight[c] = total_valid_pixels / (num_classes * count[c])
```

Counts are clamped to at least 1 to remain numerically stable. Validation and
test data must never be used for class-weight computation.

## Optimizer

`create_optimizer(model, config)` supports:

| Name | Default |
|------|---------|
| `adamw` | Yes |
| `sgd` | Optional (momentum=0.9) |

Uses `learning_rate` and `weight_decay` from `TrainingConfig`.

## Scheduler

`create_scheduler(optimizer, config)` supports:

| Name | Behavior |
|------|----------|
| `none` | Constant learning rate |
| `cosine` | `CosineAnnealingLR` over all epochs |

The scheduler is stepped **once per epoch** after the training pass completes.

## Metrics

Pixel-level segmentation metrics are computed from a masked confusion matrix
(rows = actual, columns = predicted):

- overall accuracy
- per-class precision, recall, F1, IoU
- mean IoU
- mean F1

Nodata and invalid label pixels are excluded. Classes absent from a batch
return zero for division-safe precision/recall/F1/IoU.

## Checkpoint Format

Checkpoints are saved atomically to:

```text
checkpoint_dir/latest.pt
checkpoint_dir/best.pt
training_history.json
```

Each checkpoint contains:

- `model_state_dict`
- `optimizer_state_dict`
- `scheduler_state_dict`
- `epoch`
- `best_validation_loss`
- `training_config`
- `model_config`
- `training_history`
- `seed`

Loading validates `in_channels` and `num_classes` compatibility.

## Early Stopping

Early stopping monitors **validation loss**.

Improvement is defined as:

```text
new_loss < best_loss - min_delta
```

If validation loss fails to improve by at least `min_delta` for
`early_stopping_patience` consecutive epochs, training stops. The best checkpoint
remains available on disk.

## Reproducibility

`set_global_seed(seed)` seeds Python, NumPy, and PyTorch (CPU and CUDA when
available). CuDNN deterministic mode is enabled.

Some GPU kernels may remain nondeterministic depending on hardware/backend.
CPU training with a fixed seed and data order is generally reproducible.

## Device Selection

`resolve_device("auto")` selects CUDA when available, otherwise CPU.

| Value | Behavior |
|-------|----------|
| `auto` | CUDA if available, else CPU |
| `cpu` | CPU only |
| `cuda` | CUDA required; raises if unavailable |

Tensors and models are moved with `.to(device)`. No forced `.cuda()` calls.

## Example Training Script

```python
from ssri_model.architecture import create_ssri_model
from ssri_model.ml import SSRIDataset, create_dataloader
from ssri_model.training import TrainingConfig, Trainer

dataset_root = "./data/my-dataset"
train_ds = SSRIDataset(dataset_root, split="train")
val_ds = SSRIDataset(dataset_root, split="validation")

train_loader = create_dataloader(train_ds, batch_size=4)
val_loader = create_dataloader(val_ds, batch_size=4)

model = create_ssri_model()
config = TrainingConfig(
    epochs=20,
    batch_size=4,
    learning_rate=1e-3,
    checkpoint_dir="./checkpoints/run-001",
    device="auto",
    seed=42,
)
trainer = Trainer(model=model, config=config)
result = trainer.fit(train_loader, val_loader)
print(result.best_epoch, result.best_validation_loss)
```

## Known Limitations

- Single-device training only (no distributed/multi-GPU)
- No experiment tracking (W&B, TensorBoard, MLflow)
- No test-set evaluation during training
- Baseline loss is cross entropy only (no Dice/Focal extensions yet)
- Successful training on synthetic data does not imply scientific accuracy
- This baseline model is not yet validated on real labeled hazard data

## Future Extension Points

- Additional segmentation losses (Dice, Focal, Lovász)
- Auxiliary prediction heads
- Mixed precision training
- Test-set evaluation stage (Stage 2.5+)
- CLI entry point and experiment tracking integration

## Package Structure

```text
training/
├── __init__.py
├── config.py
├── losses.py
├── metrics.py
├── optimizer.py
├── scheduler.py
├── checkpoint.py
├── trainer.py
├── history.py
├── reproducibility.py
└── exceptions.py
```
