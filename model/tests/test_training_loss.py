"""Tests for SSRI masked cross entropy loss."""

from __future__ import annotations

import torch
import pytest

from ssri_model.ml.constants import LABEL_NODATA
from ssri_model.training.exceptions import LossComputationError, NoValidPixelsError
from ssri_model.training.losses import compute_class_weights, masked_cross_entropy
from tests.training_helpers import SyntheticSegmentationDataset


class TestMaskedCrossEntropy:
    def test_valid_masked_loss(self) -> None:
        logits = torch.randn(2, 3, 4, 4)
        targets = torch.randint(0, 3, (2, 4, 4))
        mask = torch.ones(2, 4, 4, dtype=torch.bool)
        loss = masked_cross_entropy(logits, targets, mask)
        assert loss.ndim == 0
        assert torch.isfinite(loss)

    def test_correct_shape_contract(self) -> None:
        logits = torch.randn(1, 3, 8, 8)
        targets = torch.zeros(1, 8, 8, dtype=torch.int64)
        mask = torch.ones(1, 8, 8, dtype=torch.bool)
        loss = masked_cross_entropy(logits, targets, mask)
        assert loss.shape == torch.Size([])

    def test_nodata_exclusion(self) -> None:
        logits = torch.zeros(1, 3, 2, 2)
        logits[:, 0, :, :] = 5.0
        targets = torch.full((1, 2, 2), LABEL_NODATA, dtype=torch.int64)
        targets[0, 0, 0] = 0
        mask = torch.ones(1, 2, 2, dtype=torch.bool)
        loss = masked_cross_entropy(logits, targets, mask)
        assert torch.isfinite(loss)

    def test_all_valid_pixels(self) -> None:
        logits = torch.randn(2, 3, 5, 5)
        targets = torch.randint(0, 3, (2, 5, 5))
        mask = torch.ones(2, 5, 5, dtype=torch.bool)
        loss = masked_cross_entropy(logits, targets, mask)
        assert float(loss.item()) >= 0.0

    def test_partially_masked_pixels(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.randint(0, 3, (1, 4, 4))
        mask = torch.ones(1, 4, 4, dtype=torch.bool)
        mask[:, :2, :] = False
        loss = masked_cross_entropy(logits, targets, mask)
        assert torch.isfinite(loss)

    def test_zero_valid_pixels_raises(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.randint(0, 3, (1, 4, 4))
        mask = torch.zeros(1, 4, 4, dtype=torch.bool)
        with pytest.raises(NoValidPixelsError):
            masked_cross_entropy(logits, targets, mask)

    def test_class_weights(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.zeros(1, 4, 4, dtype=torch.int64)
        mask = torch.ones(1, 4, 4, dtype=torch.bool)
        weights = torch.tensor([1.0, 2.0, 3.0])
        loss = masked_cross_entropy(logits, targets, mask, class_weights=weights)
        assert torch.isfinite(loss)

    def test_invalid_logit_shape(self) -> None:
        logits = torch.randn(2, 3, 4)
        targets = torch.zeros(2, 4, 4, dtype=torch.int64)
        mask = torch.ones(2, 4, 4, dtype=torch.bool)
        with pytest.raises(LossComputationError):
            masked_cross_entropy(logits, targets, mask)

    def test_invalid_target_shape(self) -> None:
        logits = torch.randn(2, 3, 4, 4)
        targets = torch.zeros(2, 4, dtype=torch.int64)
        mask = torch.ones(2, 4, 4, dtype=torch.bool)
        with pytest.raises(LossComputationError):
            masked_cross_entropy(logits, targets, mask)

    def test_invalid_mask_dtype(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.zeros(1, 4, 4, dtype=torch.int64)
        mask = torch.ones(1, 4, 4, dtype=torch.float32)
        with pytest.raises(LossComputationError):
            masked_cross_entropy(logits, targets, mask)

    def test_invalid_class_labels(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        targets = torch.full((1, 4, 4), 5, dtype=torch.int64)
        mask = torch.ones(1, 4, 4, dtype=torch.bool)
        with pytest.raises(NoValidPixelsError):
            masked_cross_entropy(logits, targets, mask)

    def test_finite_loss(self) -> None:
        logits = torch.randn(2, 3, 8, 8)
        targets = torch.randint(0, 3, (2, 8, 8))
        mask = torch.ones(2, 8, 8, dtype=torch.bool)
        loss = masked_cross_entropy(logits, targets, mask)
        assert torch.isfinite(loss).item()

    def test_masked_logits_do_not_change_loss(self) -> None:
        logits_a = torch.randn(1, 3, 4, 4)
        logits_b = logits_a.clone()
        targets = torch.randint(0, 3, (1, 4, 4))
        mask = torch.ones(1, 4, 4, dtype=torch.bool)
        mask[:, 0, :] = False

        logits_b[:, :, 0, :] = 999.0
        loss_a = masked_cross_entropy(logits_a, targets, mask)
        loss_b = masked_cross_entropy(logits_b, targets, mask)
        assert torch.allclose(loss_a, loss_b)

    def test_wrong_class_count(self) -> None:
        logits = torch.randn(1, 2, 4, 4)
        targets = torch.zeros(1, 4, 4, dtype=torch.int64)
        mask = torch.ones(1, 4, 4, dtype=torch.bool)
        with pytest.raises(LossComputationError):
            masked_cross_entropy(logits, targets, mask, num_classes=3)


class TestComputeClassWeights:
    def test_compute_class_weights_from_train_dataset(self) -> None:
        dataset = SyntheticSegmentationDataset(num_samples=4, height=8, width=8, seed=1)
        weights = compute_class_weights(dataset)
        assert weights.shape == (3,)
        assert torch.all(weights > 0)

    def test_empty_dataset_raises(self) -> None:
        dataset = SyntheticSegmentationDataset(
            num_samples=1,
            height=4,
            width=4,
            seed=2,
            masked_fraction=1.0,
        )
        with pytest.raises(NoValidPixelsError):
            compute_class_weights(dataset)
