"""Shared constants for SSRI machine learning workflows."""

from __future__ import annotations

from ssri_model.ml.labels import LabelClass

DEFAULT_RANDOM_SEED = 42
DEFAULT_RESOLUTION = 30.0

# Stage 1 nodata sentinel used across feature channels.
FEATURE_NODATA = -9999.0

# Integer label tensor value reserved for nodata / ignore pixels.
LABEL_NODATA = -1

DEFAULT_SPLIT: dict[str, float] = {
    "train": 0.70,
    "validation": 0.15,
    "test": 0.15,
}

CHANNEL_NAMES: tuple[str, ...] = (
    "elevation",
    "slope",
    "plan_curvature",
    "profile_curvature",
    "twi",
    "relative_relief",
    "valley_depth",
    "ndvi",
    "ndwi",
    "clay_mineral_ratio",
    "iron_oxide_index",
    "gravity",
    "magnetics",
)

CHANNEL_COUNT = len(CHANNEL_NAMES)

SUPPORTED_LABELS: tuple[str, ...] = tuple(label.value for label in LabelClass)
