"""Tests for ECE computation (synthetic math only — not scientific validation)."""

from __future__ import annotations

import numpy as np

from ssri_model.evaluation.calibration_ece import expected_calibration_error


def test_ece_perfectly_calibrated_is_near_zero() -> None:
    rng = np.random.default_rng(0)
    probs = rng.uniform(0.0, 1.0, size=5000)
    labels = (rng.uniform(0.0, 1.0, size=5000) < probs).astype(np.float64)
    result = expected_calibration_error(probs, labels, n_bins=10)
    assert result.ece < 0.05


def test_ece_constant_wrong_is_high() -> None:
    probs = np.full(1000, 0.9)
    labels = np.zeros(1000)
    result = expected_calibration_error(probs, labels, n_bins=10)
    assert result.ece > 0.8
