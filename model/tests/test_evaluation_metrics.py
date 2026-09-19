"""Tests for SSRI evaluation metrics."""

from __future__ import annotations

import math

import torch
import pytest

from ssri_model.evaluation.metrics import (
    compute_evaluation_metrics,
    compute_evaluation_metrics_from_confusion,
)
from ssri_model.ml.constants import LABEL_NODATA


class TestEvaluationMetrics:
    def test_perfect_prediction(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 0, :, :] = 10.0
        targets = torch.zeros(1, 2, 2, dtype=torch.int64)
        mask = torch.ones(1, 2, 2, dtype=torch.bool)
        metrics = compute_evaluation_metrics(logits, targets, mask)
        assert metrics.accuracy == pytest.approx(1.0)
        assert metrics.macro_f1 == pytest.approx(1.0 / 3.0, rel=1e-5)

    def test_completely_wrong_prediction(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 1, :, :] = 10.0
        targets = torch.zeros(1, 2, 2, dtype=torch.int64)
        mask = torch.ones(1, 2, 2, dtype=torch.bool)
        metrics = compute_evaluation_metrics(logits, targets, mask)
        assert metrics.accuracy == pytest.approx(0.0)

    def test_nodata_exclusion(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 0, 0, 0] = 10.0
        targets = torch.tensor([[[0, 1], [2, 0]]], dtype=torch.int64)
        mask = torch.tensor([[[True, False], [True, True]]])
        metrics = compute_evaluation_metrics(logits, targets, mask)
        assert metrics.valid_pixel_count == 3

    def test_mask_exclusion(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.randint(0, 3, (1, 4, 4))
        mask = torch.zeros(1, 4, 4, dtype=torch.bool)
        mask[:, 2:, :] = True
        metrics = compute_evaluation_metrics(logits, targets, mask)
        assert metrics.valid_pixel_count == 8

    def test_absent_classes(self) -> None:
        confusion = torch.tensor([[4, 0, 0], [0, 0, 0], [0, 0, 0]])
        metrics = compute_evaluation_metrics_from_confusion(confusion)
        assert metrics.classes["landslide"].precision == 0.0
        assert not math.isnan(metrics.macro_precision)

    def test_confusion_matrix(self) -> None:
        confusion = torch.tensor([[2, 0, 0], [0, 1, 0], [0, 0, 1]])
        metrics = compute_evaluation_metrics_from_confusion(confusion)
        assert metrics.confusion_matrix[0][0] == 2

    def test_macro_f1_and_mean_iou(self) -> None:
        confusion = torch.tensor([[1, 0, 0], [0, 1, 0], [0, 0, 1]])
        metrics = compute_evaluation_metrics_from_confusion(confusion)
        assert metrics.macro_f1 == pytest.approx(1.0)
        assert metrics.mean_iou == pytest.approx(1.0)

    def test_no_nans(self) -> None:
        logits = torch.randn(2, 3, 4, 4)
        targets = torch.randint(0, 3, (2, 4, 4))
        mask = torch.ones(2, 4, 4, dtype=torch.bool)
        metrics = compute_evaluation_metrics(logits, targets, mask)
        assert metrics.accuracy == metrics.accuracy
        assert metrics.macro_precision == metrics.macro_precision

    def test_label_nodata_excluded(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 0, :, :] = 10.0
        targets = torch.full((1, 2, 2), LABEL_NODATA, dtype=torch.int64)
        targets[0, 0, 0] = 0
        mask = torch.ones(1, 2, 2, dtype=torch.bool)
        metrics = compute_evaluation_metrics(logits, targets, mask)
        assert metrics.valid_pixel_count == 1
