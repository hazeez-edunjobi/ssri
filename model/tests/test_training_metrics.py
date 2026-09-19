"""Tests for SSRI segmentation metrics."""

from __future__ import annotations

import torch
import pytest

from ssri_model.training.exceptions import MetricsComputationError
from ssri_model.training.metrics import (
    compute_metrics_from_confusion,
    compute_segmentation_metrics,
    masked_confusion_matrix,
)


class TestConfusionMatrix:
    def test_basic_confusion_matrix(self) -> None:
        predictions = torch.tensor([[0, 1], [2, 0]])
        targets = torch.tensor([[0, 0], [2, 1]])
        mask = torch.ones(2, 2, dtype=torch.bool)
        confusion = masked_confusion_matrix(predictions, targets, mask)
        assert confusion.shape == (3, 3)
        assert int(confusion[0, 0]) == 1
        assert int(confusion[2, 2]) == 1

    def test_nodata_exclusion(self) -> None:
        predictions = torch.tensor([[0, 1], [2, 0]])
        targets = torch.tensor([[0, 0], [2, 1]])
        mask = torch.tensor([[True, False], [True, True]])
        confusion = masked_confusion_matrix(predictions, targets, mask)
        assert int(confusion.sum()) == 3

    def test_empty_valid_pixels(self) -> None:
        predictions = torch.zeros(2, 2, dtype=torch.int64)
        targets = torch.zeros(2, 2, dtype=torch.int64)
        mask = torch.zeros(2, 2, dtype=torch.bool)
        confusion = masked_confusion_matrix(predictions, targets, mask)
        assert int(confusion.sum()) == 0


class TestSegmentationMetrics:
    def test_perfect_predictions(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 0, :, :] = 10.0
        targets = torch.zeros(1, 2, 2, dtype=torch.int64)
        mask = torch.ones(1, 2, 2, dtype=torch.bool)
        metrics = compute_segmentation_metrics(logits, targets, mask)
        assert metrics.accuracy == pytest.approx(1.0)
        assert metrics.mean_iou == pytest.approx(1.0 / 3.0, rel=1e-5)

    def test_accuracy(self) -> None:
        confusion = torch.tensor([[2, 1, 0], [0, 3, 0], [0, 0, 1]])
        metrics = compute_metrics_from_confusion(confusion)
        assert metrics.accuracy == pytest.approx(6.0 / 7.0)

    def test_precision_recall_f1_iou(self) -> None:
        confusion = torch.tensor([[2, 0, 0], [1, 1, 0], [0, 0, 1]])
        metrics = compute_metrics_from_confusion(confusion)
        subsidence = metrics.classes["subsidence"]
        assert subsidence.precision == pytest.approx(2.0 / 3.0)
        assert subsidence.recall == pytest.approx(1.0)
        assert subsidence.f1 > 0.0
        assert subsidence.iou > 0.0

    def test_mean_iou_and_mean_f1(self) -> None:
        confusion = torch.tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        metrics = compute_metrics_from_confusion(confusion)
        assert metrics.mean_iou == pytest.approx(1.0)
        assert metrics.mean_f1 == pytest.approx(1.0)
        assert metrics.macro_f1 == pytest.approx(1.0)

    def test_absent_class_handling(self) -> None:
        confusion = torch.tensor([[4, 0, 0], [0, 0, 0], [0, 0, 0]])
        metrics = compute_metrics_from_confusion(confusion)
        assert metrics.classes["landslide"].precision == 0.0
        assert metrics.classes["landslide"].recall == 0.0
        assert metrics.classes["landslide"].iou == 0.0

    def test_finite_outputs(self) -> None:
        logits = torch.randn(2, 3, 4, 4)
        targets = torch.randint(0, 3, (2, 4, 4))
        mask = torch.ones(2, 4, 4, dtype=torch.bool)
        metrics = compute_segmentation_metrics(logits, targets, mask)
        assert metrics.accuracy == metrics.accuracy
        assert metrics.mean_iou == metrics.mean_iou

    def test_nodata_pixels_do_not_affect_metrics(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 0, 0, 0] = 10.0
        targets = torch.tensor([[[0, 1], [2, 0]]], dtype=torch.int64)
        mask = torch.tensor([[[True, False], [True, True]]])
        metrics_full = compute_segmentation_metrics(logits, targets, mask)

        logits_alt = logits.clone()
        logits_alt[:, :, 0, 1] = 999.0
        targets_alt = targets.clone()
        targets_alt[0, 0, 1] = -1
        metrics_alt = compute_segmentation_metrics(logits_alt, targets_alt, mask)
        assert metrics_full.accuracy == metrics_alt.accuracy
        assert metrics_full.mean_iou == metrics_alt.mean_iou

    def test_invalid_prediction_range(self) -> None:
        predictions = torch.tensor([[5, 0]])
        targets = torch.tensor([[0, 1]])
        mask = torch.ones(1, 2, dtype=torch.bool)
        with pytest.raises(MetricsComputationError):
            masked_confusion_matrix(predictions, targets, mask)

    def test_metrics_to_dict(self) -> None:
        confusion = torch.tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        metrics = compute_metrics_from_confusion(confusion)
        payload = metrics.to_dict()
        assert "accuracy" in payload
        assert "classes" in payload
        assert "subsidence" in payload["classes"]
