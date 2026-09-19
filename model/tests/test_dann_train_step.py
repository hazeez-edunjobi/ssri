"""Engineering test: DANN train step runs and updates weights (synthetic tensors)."""

from __future__ import annotations

import torch

from ssri_model.architecture.multitask import SSRIMultiTaskModel
from ssri_model.dann.train_step import _dummy_batch, dann_train_step


def test_dann_train_step_reduces_or_runs() -> None:
    model = SSRIMultiTaskModel(dann=True)
    opt = torch.optim.Adam(model.parameters(), lr=1e-3)
    source, targets, masks, target = _dummy_batch()
    before = sum(p.detach().sum().item() for p in model.parameters())
    result = dann_train_step(
        model,
        source_features=source,
        source_targets=targets,
        source_masks=masks,
        target_features=target,
        optimizer=opt,
    )
    after = sum(p.detach().sum().item() for p in model.parameters())
    assert result.total_loss == result.total_loss  # not NaN
    assert before != after or result.total_loss == 0.0
