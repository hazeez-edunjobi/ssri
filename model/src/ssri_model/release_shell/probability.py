"""Shared Stage 2.5 probability transform (softmax over mutually exclusive classes)."""

from __future__ import annotations

import torch
import torch.nn.functional as F


def logits_to_class_probabilities(logits: torch.Tensor) -> torch.Tensor:
    """Match evaluation contract: softmax over class dimension."""
    return F.softmax(logits, dim=1)


def logits_to_legacy_sigmoid(logits: torch.Tensor) -> torch.Tensor:
    """Legacy assess path (mutually exclusive CE classes — incorrect for Stage 2.5)."""
    return torch.sigmoid(logits)
