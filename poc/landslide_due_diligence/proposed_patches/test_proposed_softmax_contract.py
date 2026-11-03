"""Proposed test — NOT installed into production test path by this task.

Copy into model/tests/ only after owner approval.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def probabilities_from_logits_softmax(logits: torch.Tensor) -> torch.Tensor:
    return F.softmax(logits, dim=1)


def test_assess_eval_probability_contract_agreement():
    torch.manual_seed(0)
    logits = torch.randn(2, 3, 4, 4)
    soft = probabilities_from_logits_softmax(logits)
    # Proposed assess path must match eval: softmax, sum≈1
    assert torch.allclose(soft.sum(dim=1), torch.ones(2, 4, 4), atol=1e-5)
    sig = torch.sigmoid(logits)
    assert not torch.allclose(sig.sum(dim=1), torch.ones(2, 4, 4), atol=1e-3)
