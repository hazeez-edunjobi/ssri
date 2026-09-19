"""Evaluation metrics for SSRI test-set evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import torch

from ssri_model.training.metrics import (
    ClassMetrics,
    SegmentationMetrics,
    compute_metrics_from_confusion,
    compute_segmentation_metrics,
    masked_confusion_matrix,
)


@dataclass(frozen=True)
class EvaluationMetrics:
    """Extended segmentation metrics for evaluation reporting."""

    accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    mean_iou: float
    classes: dict[str, ClassMetrics]
    confusion_matrix: tuple[tuple[int, ...], ...]
    valid_pixel_count: int

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable metrics dictionary."""
        return {
            "accuracy": self.accuracy,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "mean_iou": self.mean_iou,
            "valid_pixel_count": self.valid_pixel_count,
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


def _macro_average(values: dict[str, ClassMetrics], attribute: str) -> float:
    if not values:
        return 0.0
    total = sum(getattr(metrics, attribute) for metrics in values.values())
    return float(total / float(len(values)))


def evaluation_metrics_from_segmentation(
    metrics: SegmentationMetrics,
    *,
    valid_pixel_count: int,
) -> EvaluationMetrics:
    """Convert training segmentation metrics to evaluation metrics."""
    return EvaluationMetrics(
        accuracy=metrics.accuracy,
        macro_precision=_macro_average(metrics.classes, "precision"),
        macro_recall=_macro_average(metrics.classes, "recall"),
        macro_f1=metrics.macro_f1,
        mean_iou=metrics.mean_iou,
        classes=metrics.classes,
        confusion_matrix=metrics.confusion_matrix,
        valid_pixel_count=valid_pixel_count,
    )


def compute_evaluation_metrics(
    logits: torch.Tensor,
    targets: torch.Tensor,
    mask: torch.Tensor,
    *,
    num_classes: int = 3,
) -> EvaluationMetrics:
    """Compute mask-aware evaluation metrics from model logits."""
    segmentation = compute_segmentation_metrics(
        logits,
        targets,
        mask,
        num_classes=num_classes,
    )
    confusion = masked_confusion_matrix(
        logits.argmax(dim=1),
        targets,
        mask,
        num_classes=num_classes,
    )
    valid_pixel_count = int(confusion.sum().item())
    return evaluation_metrics_from_segmentation(
        segmentation,
        valid_pixel_count=valid_pixel_count,
    )


def compute_evaluation_metrics_from_confusion(
    confusion: torch.Tensor,
) -> EvaluationMetrics:
    """Compute evaluation metrics from an aggregated confusion matrix."""
    segmentation = compute_metrics_from_confusion(confusion)
    valid_pixel_count = int(confusion.sum().item())
    return evaluation_metrics_from_segmentation(
        segmentation,
        valid_pixel_count=valid_pixel_count,
    )
