"""Loss functions for SSRI segmentation training."""

from __future__ import annotations

from typing import Protocol, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

from ssri_model.ml.constants import LABEL_NODATA
from ssri_model.training.exceptions import LossComputationError, NoValidPixelsError


class LabeledDataset(Protocol):
    """Dataset protocol for class-weight computation."""

    def __len__(self) -> int: ...

    def __getitem__(self, index: int) -> dict[str, torch.Tensor]: ...


def build_valid_mask(
    targets: torch.Tensor,
    mask: torch.Tensor,
    *,
    num_classes: int,
) -> torch.Tensor:
    """Return a boolean mask of pixels that contribute to loss and metrics."""
    if targets.shape != mask.shape:
        raise LossComputationError(
            "targets and mask must share shape; "
            f"received targets={tuple(targets.shape)} mask={tuple(mask.shape)}"
        )
    if targets.dtype not in (torch.int64, torch.int32, torch.long):
        raise LossComputationError(
            f"targets must be an integer tensor, received dtype={targets.dtype}"
        )
    if mask.dtype != torch.bool:
        raise LossComputationError(
            f"mask must be a boolean tensor, received dtype={mask.dtype}"
        )

    in_range = (targets >= 0) & (targets < num_classes)
    return mask & in_range & (targets != LABEL_NODATA)


def compute_class_weights(
    dataset: LabeledDataset,
    *,
    num_classes: int = 3,
) -> torch.Tensor:
    """Compute inverse-frequency class weights from training labels only.

    Only valid, in-range label pixels contribute. The weight for class ``c`` is:

    ``total_valid_pixels / (num_classes * count[c])``

    When a class is absent, its count is clamped to 1 to keep weights finite.
    """
    counts = torch.zeros(num_classes, dtype=torch.float64)
    for index in range(len(dataset)):
        sample = dataset[index]
        labels = sample["label"]
        mask = sample["mask"]
        valid = build_valid_mask(labels, mask, num_classes=num_classes)
        if not bool(valid.any()):
            continue
        valid_labels = labels[valid].to(dtype=torch.int64)
        for class_index in range(num_classes):
            counts[class_index] += int((valid_labels == class_index).sum().item())

    total = counts.sum()
    if total <= 0.0:
        raise NoValidPixelsError(
            "Cannot compute class weights because the training dataset "
            "contains no valid labeled pixels"
        )

    weights = total / (float(num_classes) * counts.clamp(min=1.0))
    return weights.to(dtype=torch.float32)


def masked_cross_entropy(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    *,
    class_weights: torch.Tensor | Sequence[float] | None = None,
    num_classes: int = 3,
) -> torch.Tensor:
    """Compute mask-aware multi-class cross entropy over segmentation logits.

    Only pixels where ``mask`` is True and ``targets`` are valid hazard classes
    contribute to the loss. Nodata label pixels are excluded.
    """
    if logits.ndim != 4:
        raise LossComputationError(
            f"Expected logits shape (B, C, H, W), received ndim={logits.ndim}"
        )
    if logits.shape[1] != num_classes:
        raise LossComputationError(
            f"Expected {num_classes} logit channels, received {logits.shape[1]}"
        )
    if targets.ndim != 3:
        raise LossComputationError(
            f"Expected targets shape (B, H, W), received ndim={targets.ndim}"
        )
    if logits.shape[0] != targets.shape[0] or logits.shape[-2:] != targets.shape[-2:]:
        raise LossComputationError(
            "logits and targets must share batch and spatial dimensions; "
            f"received logits={tuple(logits.shape)} targets={tuple(targets.shape)}"
        )

    valid = build_valid_mask(targets, mask, num_classes=num_classes)
    if not bool(valid.any()):
        raise NoValidPixelsError(
            "Cannot compute masked cross entropy because no valid pixels remain"
        )

    weight_tensor: torch.Tensor | None = None
    if class_weights is not None:
        weight_tensor = torch.as_tensor(
            class_weights,
            dtype=logits.dtype,
            device=logits.device,
        )
        if weight_tensor.numel() != num_classes:
            raise LossComputationError(
                f"class_weights must contain {num_classes} values, "
                f"received {weight_tensor.numel()}"
            )

    safe_targets = targets.clone()
    safe_targets[~valid] = 0

    per_pixel_loss = F.cross_entropy(
        logits,
        safe_targets,
        weight=weight_tensor,
        reduction="none",
    )
    return per_pixel_loss[valid].mean()


class MaskedCrossEntropyLoss(nn.Module):
    """Mask-aware cross entropy loss module for SSRI segmentation."""

    def __init__(
        self,
        *,
        class_weights: torch.Tensor | Sequence[float] | None = None,
        num_classes: int = 3,
    ) -> None:
        super().__init__()
        self.num_classes = num_classes
        if class_weights is None:
            self.register_buffer("class_weights", None)
        else:
            weights = torch.as_tensor(class_weights, dtype=torch.float32)
            if weights.numel() != num_classes:
                raise LossComputationError(
                    f"class_weights must contain {num_classes} values, "
                    f"received {weights.numel()}"
                )
            self.register_buffer("class_weights", weights)

    def forward(
        self,
        logits: torch.Tensor,
        targets: torch.Tensor,
        mask: torch.Tensor,
    ) -> torch.Tensor:
        """Compute masked cross entropy for one batch."""
        weights = self.class_weights
        if isinstance(weights, torch.Tensor):
            weight_arg: torch.Tensor | Sequence[float] | None = weights
        else:
            weight_arg = None
        return masked_cross_entropy(
            logits,
            targets,
            mask,
            class_weights=weight_arg,
            num_classes=self.num_classes,
        )
