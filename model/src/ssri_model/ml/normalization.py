"""Normalization configuration for SSRI feature channels."""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING, Mapping

from ssri_model.ml.constants import CHANNEL_NAMES

if TYPE_CHECKING:
    import numpy as np

    from ssri_model.ml.statistics_loader import ChannelStatistics, FeatureStatistics


class NormalizationMethod(str, Enum):
    """Supported per-channel normalization strategies."""

    MIN_MAX = "min_max"
    Z_SCORE = "z_score"
    IDENTITY = "identity"


# Configuration-only defaults: statistics are computed later during training prep.
CHANNEL_NORMALIZATION: dict[str, NormalizationMethod] = {
    # Terrain: absolute or wide dynamic range → z-score; bounded slope → min-max.
    "elevation": NormalizationMethod.Z_SCORE,
    "slope": NormalizationMethod.MIN_MAX,
    "plan_curvature": NormalizationMethod.Z_SCORE,
    "profile_curvature": NormalizationMethod.Z_SCORE,
    "twi": NormalizationMethod.Z_SCORE,
    "relative_relief": NormalizationMethod.MIN_MAX,
    "valley_depth": NormalizationMethod.MIN_MAX,
    # Spectral indices: already scaled ratios → identity (stats optional later).
    "ndvi": NormalizationMethod.IDENTITY,
    "ndwi": NormalizationMethod.IDENTITY,
    "clay_mineral_ratio": NormalizationMethod.Z_SCORE,
    "iron_oxide_index": NormalizationMethod.Z_SCORE,
    # Geophysics: regional anomalies with varying units → z-score.
    "gravity": NormalizationMethod.Z_SCORE,
    "magnetics": NormalizationMethod.Z_SCORE,
}


@dataclass(frozen=True)
class NormalizationConfig:
    """Normalization strategy map for all feature channels."""

    channel_methods: Mapping[str, NormalizationMethod]

    @classmethod
    def default(cls) -> NormalizationConfig:
        """Return the canonical Stage 2 normalization configuration."""
        return cls(channel_methods=dict(CHANNEL_NORMALIZATION))

    def method_for(self, channel: str) -> NormalizationMethod:
        """Return the normalization method for a channel."""
        if channel not in self.channel_methods:
            raise KeyError(f"No normalization method configured for channel: {channel}")
        return self.channel_methods[channel]

    def as_dict(self) -> dict[str, str]:
        """Serialize normalization methods to string values."""
        return {
            channel: method.value for channel, method in self.channel_methods.items()
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, str]) -> NormalizationConfig:
        """Deserialize normalization methods from string values."""
        return cls(
            channel_methods={
                channel: NormalizationMethod(method)
                for channel, method in payload.items()
            }
        )


def validate_normalization_config(config: NormalizationConfig) -> None:
    """Ensure every canonical channel has a normalization method."""
    missing = [name for name in CHANNEL_NAMES if name not in config.channel_methods]
    if missing:
        raise ValueError(
            "Normalization config missing channels: " + ", ".join(missing)
        )

    extra = [name for name in config.channel_methods if name not in CHANNEL_NAMES]
    if extra:
        raise ValueError(
            "Normalization config contains unknown channels: " + ", ".join(extra)
        )


def _safe_denominator(value: float, *, fallback: float = 1.0) -> float:
    """Return a safe denominator, avoiding zero and non-finite values."""
    if not math.isfinite(value) or abs(value) < 1e-12:
        return fallback
    return value


def normalize_channel_array(
    values: "np.ndarray",
    *,
    valid_mask: "np.ndarray",
    stats: "ChannelStatistics",
    method: NormalizationMethod,
) -> "np.ndarray":
    """Apply per-channel normalization without contaminating nodata pixels."""
    import numpy as np

    from ssri_model.ml.exceptions import NormalizationError

    if values.shape != valid_mask.shape:
        raise NormalizationError(
            "Valid mask shape must match channel array shape for normalization"
        )

    normalized = values.astype(np.float32, copy=True)
    if method is NormalizationMethod.IDENTITY:
        normalized[~valid_mask] = 0.0
        return normalized

    if method is NormalizationMethod.Z_SCORE:
        std = _safe_denominator(stats.std)
        normalized[valid_mask] = (values[valid_mask] - stats.mean) / std
    elif method is NormalizationMethod.MIN_MAX:
        denom = _safe_denominator(stats.max - stats.min)
        normalized[valid_mask] = (values[valid_mask] - stats.min) / denom
    else:
        raise NormalizationError(f"Unsupported normalization method: {method}")

    normalized[~valid_mask] = 0.0
    if not np.isfinite(normalized[valid_mask]).all():
        raise NormalizationError(
            "Normalization produced non-finite values for valid pixels"
        )
    return normalized


def normalize_feature_stack(
    tensor: "np.ndarray",
    *,
    valid_mask: "np.ndarray",
    statistics: "FeatureStatistics",
    config: NormalizationConfig,
) -> "np.ndarray":
    """Normalize a ``(C, H, W)`` feature stack using precomputed statistics."""
    import numpy as np

    from ssri_model.ml.constants import CHANNEL_COUNT
    from ssri_model.ml.exceptions import NormalizationError

    if tensor.shape[0] != CHANNEL_COUNT:
        raise NormalizationError(
            f"Expected {CHANNEL_COUNT} channels for normalization, received {tensor.shape[0]}"
        )

    output = np.empty_like(tensor, dtype=np.float32)
    for index, channel_name in enumerate(CHANNEL_NAMES):
        method = config.method_for(channel_name)
        output[index] = normalize_channel_array(
            tensor[index],
            valid_mask=valid_mask,
            stats=statistics.for_channel(channel_name),
            method=method,
        )
    return output
