"""Tests for PRD multi-task model + masked BCE (missing labels stay missing)."""

from __future__ import annotations

import torch

from ssri_model.architecture.multitask import (
    SSRIMultiTaskModel,
    masked_multitask_bce_with_logits,
)
from ssri_model.ml.constants import CHANNEL_COUNT


def test_multitask_forward_shapes() -> None:
    model = SSRIMultiTaskModel(dann=True)
    x = torch.randn(2, CHANNEL_COUNT, 32, 32)
    logits, domain = model(x, return_domain_logit=True)
    assert set(logits) == {"landslide", "subsidence", "liquefaction"}
    for tensor in logits.values():
        assert tensor.shape == (2, 32, 32)
    assert domain.shape == (2,)


def test_masked_bce_ignores_missing_task() -> None:
    model = SSRIMultiTaskModel(dann=False)
    x = torch.randn(1, CHANNEL_COUNT, 16, 16, requires_grad=True)
    logits = model(x)
    targets = {
        "landslide": torch.ones(1, 16, 16),
        "subsidence": torch.zeros(1, 16, 16),
        "liquefaction": torch.zeros(1, 16, 16),
    }
    masks = {
        "landslide": torch.ones(1, 16, 16),
        "subsidence": torch.zeros(1, 16, 16),  # missing — must not train as negative
        "liquefaction": torch.zeros(1, 16, 16),
    }
    loss = masked_multitask_bce_with_logits(logits, targets, masks)
    loss.backward()
    assert torch.isfinite(loss)
