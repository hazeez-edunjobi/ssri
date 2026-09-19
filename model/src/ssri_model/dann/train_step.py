"""Synthetic DANN training step (engineering only — not scientific validation)."""

from __future__ import annotations

from dataclasses import dataclass

import torch
import torch.nn.functional as F
from torch import nn

from ssri_model.architecture.multitask import (
    SSRIMultiTaskModel,
    masked_multitask_bce_with_logits,
)
from ssri_model.dann import DannLossWeights, dann_total_loss
from ssri_model.ml.constants import CHANNEL_COUNT


@dataclass
class DannTrainStepResult:
    total_loss: float
    task_loss: float
    domain_loss: float


def dann_train_step(
    model: SSRIMultiTaskModel,
    *,
    source_features: torch.Tensor,
    source_targets: dict[str, torch.Tensor],
    source_masks: dict[str, torch.Tensor],
    target_features: torch.Tensor,
    optimizer: torch.optim.Optimizer,
    weights: DannLossWeights | None = None,
) -> DannTrainStepResult:
    """One adversarial step: labelled source + unlabelled target.

    Domain labels: source=0, target=1. Task loss uses masked BCE on source only.
    """
    if not model.dann_enabled:
        raise ValueError("SSRIMultiTaskModel must be constructed with dann=True")

    model.train()
    optimizer.zero_grad(set_to_none=True)

    source_logits, source_domain = model(source_features, return_domain_logit=True)
    _target_logits, target_domain = model(target_features, return_domain_logit=True)

    task_loss = masked_multitask_bce_with_logits(
        source_logits, source_targets, source_masks
    )
    domain_logits = torch.cat([source_domain, target_domain], dim=0)
    domain_labels = torch.cat(
        [
            torch.zeros(source_features.shape[0], device=domain_logits.device),
            torch.ones(target_features.shape[0], device=domain_logits.device),
        ],
        dim=0,
    )
    domain_loss = F.binary_cross_entropy_with_logits(domain_logits, domain_labels)
    total = dann_total_loss(task_loss, domain_loss, weights=weights)
    total.backward()
    optimizer.step()
    return DannTrainStepResult(
        total_loss=float(total.detach()),
        task_loss=float(task_loss.detach()),
        domain_loss=float(domain_loss.detach()),
    )


def _dummy_batch(batch: int = 2, size: int = 16) -> tuple[
    torch.Tensor,
    dict[str, torch.Tensor],
    dict[str, torch.Tensor],
    torch.Tensor,
]:
    source = torch.randn(batch, CHANNEL_COUNT, size, size)
    target = torch.randn(batch, CHANNEL_COUNT, size, size)
    targets = {
        "landslide": torch.randint(0, 2, (batch, size, size)).float(),
        "subsidence": torch.zeros(batch, size, size),
        "liquefaction": torch.zeros(batch, size, size),
    }
    masks = {
        "landslide": torch.ones(batch, size, size),
        "subsidence": torch.zeros(batch, size, size),
        "liquefaction": torch.zeros(batch, size, size),
    }
    return source, targets, masks, target
