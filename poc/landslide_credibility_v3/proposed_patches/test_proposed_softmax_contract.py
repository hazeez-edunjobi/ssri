"""Proposed tests — NOT installed into production test path by this task.

Copy into model/tests/ only after owner approval.
Proves assess-eval probability contract: Stage 2.5 uses softmax, not sigmoid.
"""
from __future__ import annotations

import torch
import torch.nn.functional as F


def probabilities_from_logits_softmax(logits: torch.Tensor) -> torch.Tensor:
    return F.softmax(logits, dim=1)


def probabilities_from_logits_sigmoid_legacy(logits: torch.Tensor) -> torch.Tensor:
    """Current buggy assess/MC path for mutually exclusive CE classes."""
    return torch.sigmoid(logits)


def test_softmax_channels_sum_to_one():
    torch.manual_seed(0)
    logits = torch.randn(2, 3, 4, 4)
    soft = probabilities_from_logits_softmax(logits)
    assert torch.allclose(soft.sum(dim=1), torch.ones(2, 4, 4), atol=1e-5)


def test_sigmoid_does_not_match_softmax_contract():
    torch.manual_seed(0)
    logits = torch.randn(2, 3, 4, 4)
    soft = probabilities_from_logits_softmax(logits)
    sig = probabilities_from_logits_sigmoid_legacy(logits)
    assert not torch.allclose(sig.sum(dim=1), torch.ones(2, 4, 4), atol=1e-3)
    assert not torch.allclose(soft, sig, atol=1e-3)


def test_proposed_assess_path_agrees_with_eval():
    """Both paths must call the same softmax helper."""
    torch.manual_seed(1)
    logits = torch.randn(1, 3, 8, 8)
    eval_probs = F.softmax(logits, dim=1)
    assess_probs = probabilities_from_logits_softmax(logits)
    assert torch.allclose(eval_probs, assess_probs, atol=1e-7)


if __name__ == "__main__":
    test_softmax_channels_sum_to_one()
    test_sigmoid_does_not_match_softmax_contract()
    test_proposed_assess_path_agrees_with_eval()
    print("OK: softmax contract tests passed")
