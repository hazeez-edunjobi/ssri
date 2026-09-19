"""Segmentation metrics for SSRI training and validation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from ssri_model.ml.labels import label_class_names
from ssri_model.training.exceptions import MetricsComputationError
from ssri_model.training.losses import build_valid_mask


@dataclass(frozen=True)
class ClassMetrics:
    """Per-class segmentation metrics."""

    precision: float
    recall: float
    f1: float
    iou: float


@dataclass(frozen=True)
class SegmentationMetrics:
    """Aggregated segmentation metrics for one evaluation pass."""

    accuracy: float
    mean_iou: float
    mean_f1: float
    macro_f1: float
    classes: dict[str, ClassMetrics]
    confusion_matrix: tuple[tuple[int, ...], ...]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable metrics dictionary."""
        return {
            "accuracy": self.accuracy,
            "mean_iou": self.mean_iou,
            "mean_f1": self.mean_f1,
            "macro_f1": self.macro_f1,
            "classes": {
                name: {
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "iou": metrics.iou,
                }
                for name, metrics in self.classes.items()
            },
            "confusion_matrix": [list(row) for row in self.confusion_matrix],
        }


def masked_confusion_matrix(
    predictions: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    *,
    num_classes: int = 3,
) -> torch.Tensor:
    """Build a masked confusion matrix with rows=actual and columns=predicted."""
    if predictions.shape != targets.shape:
        raise MetricsComputationError(
            "predictions and targets must share shape; "
            f"received predictions={tuple(predictions.shape)} "
            f"targets={tuple(targets.shape)}"
        )

    valid = build_valid_mask(targets, mask, num_classes=num_classes)
    if not bool(valid.any()):
        return torch.zeros(num_classes, num_classes, dtype=torch.int64)

    valid_predictions = predictions[valid].to(dtype=torch.int64)
    valid_targets = targets[valid].to(dtype=torch.int64)
    if bool((valid_predictions < 0).any() or (valid_predictions >= num_classes).any()):
        raise MetricsComputationError(
            "predictions contain values outside the supported class range"
        )

    indices = valid_targets * num_classes + valid_predictions
    flat_counts = torch.bincount(
        indices,
        minlength=num_classes * num_classes,
    )
    return flat_counts.reshape(num_classes, num_classes).to(dtype=torch.int64)


def _safe_divide(numerator: float, denominator: float) -> float:
    if denominator <= 0.0:
        return 0.0
    return numerator / denominator


def compute_metrics_from_confusion(
    confusion: torch.Tensor,
) -> SegmentationMetrics:
    """Compute segmentation metrics from an aggregated confusion matrix."""
    if confusion.ndim != 2 or confusion.shape[0] != confusion.shape[1]:
        raise MetricsComputationError(
            "confusion matrix must be square; "
            f"received shape={tuple(confusion.shape)}"
        )

    num_classes = int(confusion.shape[0])
    confusion_cpu = confusion.to(dtype=torch.float64)
    total = float(confusion_cpu.sum().item())
    if total <= 0.0:
        class_names = label_class_names()
        empty_classes = {
            name: ClassMetrics(precision=0.0, recall=0.0, f1=0.0, iou=0.0)
            for name in class_names[:num_classes]
        }
        empty_matrix = tuple(tuple(0 for _ in range(num_classes)) for _ in range(num_classes))
        return SegmentationMetrics(
            accuracy=0.0,
            mean_iou=0.0,
            mean_f1=0.0,
            macro_f1=0.0,
            classes=empty_classes,
            confusion_matrix=empty_matrix,
        )

    accuracy = float(torch.trace(confusion_cpu).item() / total)
    class_names = label_class_names()[:num_classes]
    class_metrics: dict[str, ClassMetrics] = {}
    iou_values: list[float] = []
    f1_values: list[float] = []

    for class_index, class_name in enumerate(class_names):
        true_positive = float(confusion_cpu[class_index, class_index].item())
        false_positive = float(confusion_cpu[:, class_index].sum().item() - true_positive)
        false_negative = float(confusion_cpu[class_index, :].sum().item() - true_positive)

        precision = _safe_divide(true_positive, true_positive + false_positive)
        recall = _safe_divide(true_positive, true_positive + false_negative)
        f1 = _safe_divide(2.0 * precision * recall, precision + recall)
        iou = _safe_divide(true_positive, true_positive + false_positive + false_negative)

        class_metrics[class_name] = ClassMetrics(
            precision=precision,
            recall=recall,
            f1=f1,
            iou=iou,
        )
        iou_values.append(iou)
        f1_values.append(f1)

    macro_f1_value = sum(f1_values) / float(num_classes)
    return SegmentationMetrics(
        accuracy=accuracy,
        mean_iou=sum(iou_values) / float(num_classes),
        mean_f1=macro_f1_value,
        macro_f1=macro_f1_value,
        classes=class_metrics,
        confusion_matrix=tuple(
            tuple(int(value) for value in row.tolist()) for row in confusion_cpu.to(dtype=torch.int64)
        ),
    )


def compute_segmentation_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    *,
    num_classes: int = 3,
) -> SegmentationMetrics:
    """Compute masked segmentation metrics from raw model logits."""
    predictions = logits.argmax(dim=1)
    confusion = masked_confusion_matrix(
        predictions,
        targets,
        mask,
        num_classes=num_classes,
    )
    return compute_metrics_from_confusion(confusion)
