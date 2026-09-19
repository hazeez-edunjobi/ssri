"""Domain-similarity centroid loading for assessments.

A calibrated centroid must come from a real reference embedding distribution
(``SSRI_DOMAIN_CENTROID_PATH`` → ``.npy`` of shape ``(CHANNEL_COUNT,)``).
An all-zero vector is never treated as calibrated.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.service.exceptions import InvalidServiceRequestError
from ssri_model.uncertainty import (
    DomainCentroid,
    cosine_similarity,
    normalize_similarity,
)


@dataclass(frozen=True)
class DomainSimilarityResult:
    """Outcome of domain-similarity resolution for one assessment."""

    calibrated: bool
    score: float | None
    notes: tuple[str, ...] = ()


def _centroid_path_from_env() -> Path | None:
    raw = os.getenv("SSRI_DOMAIN_CENTROID_PATH", "").strip()
    if not raw:
        return None
    return Path(raw)


def load_domain_centroid(path: Path) -> DomainCentroid:
    """Load and validate a reference-domain centroid from disk."""
    try:
        vector = np.load(path)
    except OSError as exc:
        raise InvalidServiceRequestError(
            f"Failed to load domain centroid from {path}: {exc}"
        ) from exc
    array = np.asarray(vector, dtype=np.float64).reshape(-1)
    if array.shape[0] != CHANNEL_COUNT:
        raise InvalidServiceRequestError(
            f"Domain centroid must have length {CHANNEL_COUNT}, got {array.shape[0]}"
        )
    if not np.isfinite(array).all():
        raise InvalidServiceRequestError("Domain centroid contains non-finite values")
    if np.allclose(array, 0.0):
        raise InvalidServiceRequestError(
            "Domain centroid is all-zero; refusing to treat it as calibrated. "
            "Unset SSRI_DOMAIN_CENTROID_PATH or provide a real reference embedding."
        )
    return DomainCentroid(vector=array, count=1)


def resolve_domain_similarity(embedding: np.ndarray) -> DomainSimilarityResult:
    """Resolve similarity against a configured centroid, or mark uncalibrated.

    When ``SSRI_DOMAIN_CENTROID_PATH`` is unset, returns ``calibrated=False`` and
    ``score=None``. Callers must not invent a placeholder score.
    """
    path = _centroid_path_from_env()
    if path is None:
        return DomainSimilarityResult(
            calibrated=False,
            score=None,
            notes=(
                "domain_similarity_calibrated=false",
                "domain_similarity_reason=no_SSRI_DOMAIN_CENTROID_PATH",
            ),
        )
    if not path.is_file():
        raise InvalidServiceRequestError(
            f"SSRI_DOMAIN_CENTROID_PATH does not exist or is not a file: {path}"
        )
    centroid = load_domain_centroid(path)
    raw = cosine_similarity(embedding, centroid.vector)
    score = normalize_similarity(raw)
    return DomainSimilarityResult(
        calibrated=True,
        score=float(score),
        notes=(
            "domain_similarity_calibrated=true",
            f"domain_centroid_path={path}",
        ),
    )
