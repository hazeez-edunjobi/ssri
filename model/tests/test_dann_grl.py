"""Tests for Gradient Reversal Layer (forward identity, backward −λ∇)."""

from __future__ import annotations

import torch

from ssri_model.dann import (
    DannLossWeights,
    DomainDiscriminator,
    GradientReversalLayer,
    dann_total_loss,
    global_average_pool,
    gradient_reverse,
)


def test_gradient_reverse_forward_is_identity() -> None:
    x = torch.randn(4, 8, requires_grad=True)
    y = gradient_reverse(x, lambda_=0.5)
    assert torch.allclose(y, x)


def test_gradient_reverse_backward_negates_scaled_grad() -> None:
    lam = 0.3
    x = torch.randn(2, 5, requires_grad=True)
    y = gradient_reverse(x, lambda_=lam)
    loss = y.sum()
    loss.backward()
    assert x.grad is not None
    # d(sum)/dx = 1, so grad should be -lam * 1
    assert torch.allclose(x.grad, torch.full_like(x, -lam))


def test_gradient_reversal_layer_module() -> None:
    layer = GradientReversalLayer(lambda_=1.0)
    x = torch.ones(3, 4, requires_grad=True)
    y = layer(x)
    y.sum().backward()
    assert torch.allclose(x.grad, -torch.ones_like(x))


def test_domain_discriminator_shapes() -> None:
    disc = DomainDiscriminator(in_features=16, hidden=32)
    emb = torch.randn(5, 16)
    logits = disc(emb)
    assert logits.shape == (5,)


def test_dann_total_loss_weights() -> None:
    task = torch.tensor(2.0)
    domain = torch.tensor(4.0)
    total = dann_total_loss(
        task, domain, weights=DannLossWeights(task=1.0, domain=0.5)
    )
    assert float(total) == 4.0


def test_global_average_pool() -> None:
    feat = torch.ones(2, 3, 4, 5)
    emb = global_average_pool(feat)
    assert emb.shape == (2, 3)
    assert torch.allclose(emb, torch.ones(2, 3))
