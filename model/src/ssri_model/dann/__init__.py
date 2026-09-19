"""Gradient Reversal Layer and DANN training components.

Implements Ganin et al. (2016) GRL for geological domain adaptation.

This module provides **real** adversarial building blocks. A trained DANN
checkpoint and measured transfer metrics are separate scientific milestones —
do not treat the existence of these classes as validation evidence.
"""

from __future__ import annotations

from dataclasses import dataclass

import torch
from torch import nn


class _GradientReverseFn(torch.autograd.Function):
    """Autograd function: identity forward, scaled negative gradient backward."""

    @staticmethod
    def forward(ctx, input: torch.Tensor, lambda_: float) -> torch.Tensor:  # noqa: ANN001
        ctx.lambda_ = float(lambda_)
        return input.view_as(input)

    @staticmethod
    def backward(ctx, grad_output: torch.Tensor):  # noqa: ANN001, ANN205
        return -ctx.lambda_ * grad_output, None


def gradient_reverse(x: torch.Tensor, lambda_: float = 1.0) -> torch.Tensor:
    """Apply gradient reversal with scalar ``lambda_``."""
    return _GradientReverseFn.apply(x, float(lambda_))


class GradientReversalLayer(nn.Module):
    """Module wrapper around :func:`gradient_reverse`."""

    def __init__(self, lambda_: float = 1.0) -> None:
        super().__init__()
        self.lambda_ = float(lambda_)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        return gradient_reverse(x, self.lambda_)


class DomainDiscriminator(nn.Module):
    """Binary domain classifier on pooled embeddings (source=0, target=1)."""

    def __init__(self, in_features: int, hidden: int = 128) -> None:
        super().__init__()
        if in_features <= 0:
            raise ValueError("in_features must be positive")
        self.net = nn.Sequential(
            nn.Linear(in_features, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, hidden),
            nn.ReLU(inplace=True),
            nn.Linear(hidden, 1),
        )

    def forward(self, embedding: torch.Tensor) -> torch.Tensor:
        return self.net(embedding).squeeze(-1)


@dataclass
class DannLossWeights:
    """Weights for combined DANN objective."""

    task: float = 1.0
    domain: float = 1.0


def dann_total_loss(
    task_loss: torch.Tensor,
    domain_loss: torch.Tensor,
    *,
    weights: DannLossWeights | None = None,
) -> torch.Tensor:
    """Combine task and domain losses: ``w_task * L_y + w_domain * L_d``."""
    cfg = weights or DannLossWeights()
    return cfg.task * task_loss + cfg.domain * domain_loss


def global_average_pool(feature_map: torch.Tensor) -> torch.Tensor:
    """Pool ``(B, C, H, W)`` → ``(B, C)`` embeddings for the discriminator."""
    if feature_map.ndim != 4:
        raise ValueError(f"expected NCHW tensor, got shape {tuple(feature_map.shape)}")
    return feature_map.mean(dim=(2, 3))
