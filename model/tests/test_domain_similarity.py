"""Tests for domain-similarity calibration and centroid loading."""

from __future__ import annotations

import numpy as np
import pytest

from ssri_model.api.domain_similarity import load_domain_centroid, resolve_domain_similarity
from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.service.exceptions import InvalidServiceRequestError


def test_load_domain_centroid_rejects_all_zero(tmp_path) -> None:
    path = tmp_path / "centroid.npy"
    np.save(path, np.zeros(CHANNEL_COUNT, dtype=np.float64))
    with pytest.raises(InvalidServiceRequestError, match="all-zero"):
        load_domain_centroid(path)


def test_resolve_uncalibrated_without_env(monkeypatch) -> None:
    monkeypatch.delenv("SSRI_DOMAIN_CENTROID_PATH", raising=False)
    result = resolve_domain_similarity(np.ones(CHANNEL_COUNT))
    assert result.calibrated is False
    assert result.score is None


def test_resolve_calibrated_from_real_centroid(tmp_path, monkeypatch) -> None:
    path = tmp_path / "centroid.npy"
    vector = np.linspace(0.1, 1.0, CHANNEL_COUNT, dtype=np.float64)
    np.save(path, vector)
    monkeypatch.setenv("SSRI_DOMAIN_CENTROID_PATH", str(path))
    result = resolve_domain_similarity(vector)
    assert result.calibrated is True
    assert result.score is not None
    assert result.score > 0.9


def test_all_zero_centroid_path_fails_even_if_configured(tmp_path, monkeypatch) -> None:
    """Regression: never treat an all-zero vector as a calibrated reference."""
    path = tmp_path / "zeros.npy"
    np.save(path, np.zeros(CHANNEL_COUNT, dtype=np.float64))
    monkeypatch.setenv("SSRI_DOMAIN_CENTROID_PATH", str(path))
    with pytest.raises(InvalidServiceRequestError, match="all-zero"):
        resolve_domain_similarity(np.ones(CHANNEL_COUNT))
