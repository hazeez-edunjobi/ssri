"""Tests for uncertainty quantification."""

from __future__ import annotations

import numpy as np
import torch

from ssri_model.architecture import SSRIModel, SSRIModelConfig
from ssri_model.ml.constants import CHANNEL_COUNT, SUPPORTED_LABELS
from ssri_model.uncertainty import (
    ConfidenceTier,
    DomainCentroid,
    UncertaintyConfig,
    assess_from_mc_samples,
    assign_confidence_tier,
    cosine_similarity,
    embedding_from_features,
    empirical_credible_interval,
    gradient_feature_attribution,
    normalize_similarity,
    run_mc_dropout,
)


def _tiny_model() -> SSRIModel:
    return SSRIModel(SSRIModelConfig(base_channels=8, dropout=0.2))


def test_mc_dropout_produces_multiple_samples() -> None:
    model = _tiny_model()
    features = torch.randn(1, CHANNEL_COUNT, 16, 16)
    samples = run_mc_dropout(
        model,
        features,
        config=UncertaintyConfig(mc_samples=11, dropout_p=0.2, seed=0),
    )
    assert samples.shape == (11, model.num_classes)


def test_empirical_intervals_are_ordered() -> None:
    rng = np.random.default_rng(0)
    values = rng.normal(loc=0.4, scale=0.1, size=200)
    ci80 = empirical_credible_interval(values, level=0.80)
    ci95 = empirical_credible_interval(values, level=0.95)
    assert ci80.lower <= ci80.upper
    assert ci95.lower <= ci80.lower
    assert ci95.upper >= ci80.upper


def test_mc_dropout_seeded_is_deterministic() -> None:
    model = _tiny_model()
    features = torch.randn(1, CHANNEL_COUNT, 8, 8)
    cfg = UncertaintyConfig(mc_samples=5, dropout_p=0.3, seed=123)
    a = run_mc_dropout(model, features, config=cfg)
    b = run_mc_dropout(model, features, config=cfg)
    np.testing.assert_allclose(a, b)


def test_domain_centroid_and_similarity() -> None:
    centroid = DomainCentroid(vector=np.zeros(CHANNEL_COUNT), count=0)
    emb = np.ones(CHANNEL_COUNT)
    centroid.update(emb)
    sim = normalize_similarity(cosine_similarity(emb, centroid.vector))
    assert 0.0 <= sim <= 1.0
    assert sim > 0.9


def test_confidence_tier_extrapolation() -> None:
    cfg = UncertaintyConfig()
    tier = assign_confidence_tier(
        interval_width=0.05,
        domain_similarity=0.1,
        config=cfg,
    )
    assert tier == ConfidenceTier.EXTRAPOLATION_WARNING


def test_assessment_result_from_samples() -> None:
    samples = np.array(
        [
            [0.2, 0.3, 0.1],
            [0.25, 0.35, 0.12],
            [0.22, 0.28, 0.11],
            [0.21, 0.33, 0.15],
        ]
    )
    result = assess_from_mc_samples(
        samples,
        hazard_names=SUPPORTED_LABELS,
        domain_similarity=0.8,
        domain_similarity_calibrated=True,
        assessment_id="a-1",
        primary_drivers_by_class={0: ["ndvi", "slope"], 1: ["twi"], 2: ["clay"]},
    )
    assert len(result.hazard_profiles) == 3
    payload = result.to_dict()
    assert payload["assessment_id"] == "a-1"
    assert "credible_interval_80" in payload["hazard_profiles"][0]


def test_uncalibrated_domain_similarity_nulls_score() -> None:
    samples = np.array([[0.2, 0.3, 0.1], [0.25, 0.35, 0.12]])
    result = assess_from_mc_samples(
        samples,
        hazard_names=SUPPORTED_LABELS,
        domain_similarity=None,
        domain_similarity_calibrated=False,
    )
    for profile in result.hazard_profiles:
        assert profile.domain_similarity_score is None
        assert profile.confidence_tier == ConfidenceTier.LOW


def test_gradient_attribution_returns_ranked_channels() -> None:
    model = _tiny_model()
    features = torch.randn(1, CHANNEL_COUNT, 8, 8)
    ranked = gradient_feature_attribution(model, features, class_index=0)
    assert len(ranked) == CHANNEL_COUNT
    assert ranked[0][1] >= ranked[-1][1]


def test_embedding_from_features_shape() -> None:
    features = torch.randn(2, CHANNEL_COUNT, 4, 4)
    emb = embedding_from_features(features)
    assert emb.shape == (CHANNEL_COUNT,)
