"""Release-shell: assess/eval probability contract (softmax when flag on)."""

from __future__ import annotations

import os

import torch
import torch.nn.functional as F

from ssri_model.evaluation.predictions import logits_to_probabilities
from ssri_model.release_shell.probability import logits_to_class_probabilities


def test_softmax_helper_matches_evaluation_path():
    torch.manual_seed(0)
    logits = torch.randn(2, 3, 4, 4)
    soft = logits_to_class_probabilities(logits)
    eval_probs = logits_to_probabilities(logits)
    assert torch.allclose(soft, eval_probs, atol=1e-7)
    assert torch.allclose(soft.sum(dim=1), torch.ones(2, 4, 4), atol=1e-5)
    sig = torch.sigmoid(logits)
    assert not torch.allclose(sig.sum(dim=1), torch.ones(2, 4, 4), atol=1e-3)


def test_use_assess_softmax_flag_default_off(monkeypatch):
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    monkeypatch.delenv("SSRI_ASSESS_SOFTMAX", raising=False)
    from ssri_model.release_shell.flags import use_assess_softmax

    assert use_assess_softmax() is False


def test_use_assess_softmax_flag_on(monkeypatch):
    monkeypatch.setenv("SSRI_ASSESS_SOFTMAX", "true")
    from importlib import reload

    import ssri_model.release_shell.flags as flags

    reload(flags)
    assert flags.use_assess_softmax() is True
