"""Pre-inference validation for SSRI."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np

from ssri_model.architecture.model import SSRIModel
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES
from ssri_model.ml.normalization import NormalizationConfig
from ssri_model.ml.statistics_loader import FeatureStatistics, load_feature_statistics
from ssri_model.inference.config import InferenceConfig
from ssri_model.inference.exceptions import (
    InferenceCheckpointError,
    InferenceInputError,
    InvalidInferenceConfigError,
)
from ssri_model.inference.metadata import (
    InferenceGrid,
    load_manifest_payload,
    read_inference_grid,
    validate_feature_shape,
)


@dataclass(frozen=True)
class InferenceContext:
    """Validated inference inputs."""

    grid: InferenceGrid
    statistics: FeatureStatistics
    normalization: NormalizationConfig
    feature_shape: tuple[int, int, int]
    manifest_payload: dict[str, Any]


def _read_feature_shape(feature_path: Path) -> tuple[int, int, int]:
    if not feature_path.exists():
        raise InferenceInputError(f"Feature stack not found: {feature_path}")
    try:
        array = np.load(feature_path, mmap_mode="r")
        shape = tuple(int(value) for value in array.shape)
    except OSError as exc:
        raise InferenceInputError(f"Unable to read feature stack: {feature_path}") from exc
    if len(shape) != 3:
        raise InferenceInputError(
            f"Feature stack must have shape (C, H, W), received {shape}"
        )
    return shape


def validate_inference_setup(
    config: InferenceConfig,
    *,
    model: SSRIModel | None = None,
    checkpoint_payload: dict[str, Any] | None = None,
) -> InferenceContext:
    """Validate inference inputs before running the prediction pipeline."""
    if not config.checkpoint.exists():
        raise InvalidInferenceConfigError(f"Checkpoint not found: {config.checkpoint}")
    if not config.manifest.exists():
        raise InvalidInferenceConfigError(f"Manifest not found: {config.manifest}")
    if not config.statistics.exists():
        raise InvalidInferenceConfigError(f"Statistics not found: {config.statistics}")

    grid = read_inference_grid(config.manifest)
    feature_shape = _read_feature_shape(config.features)
    validate_feature_shape(feature_shape, grid)

    if tuple(grid.channel_names) != CHANNEL_NAMES:
        raise InferenceInputError(
            "Manifest channel order does not match canonical CHANNEL_NAMES"
        )

    statistics = load_feature_statistics(config.statistics)
    if statistics.channel_count != CHANNEL_COUNT:
        raise InferenceInputError(
            f"Statistics must contain {CHANNEL_COUNT} channels, "
            f"received {statistics.channel_count}"
        )
    for channel_name in CHANNEL_NAMES:
        statistics.for_channel(channel_name)

    manifest_payload = load_manifest_payload(config.manifest)
    if "normalization" in manifest_payload and isinstance(
        manifest_payload["normalization"], dict
    ):
        normalization = NormalizationConfig.from_dict(manifest_payload["normalization"])
    else:
        normalization = NormalizationConfig.default()

    if model is not None:
        if model.in_channels != CHANNEL_COUNT:
            raise InferenceInputError(
                f"Model in_channels must be {CHANNEL_COUNT}, received {model.in_channels}"
            )
        if model.num_classes != 3:
            raise InferenceInputError(
                f"Model num_classes must be 3, received {model.num_classes}"
            )

    if checkpoint_payload is not None:
        checkpoint_identity = checkpoint_payload.get("dataset_manifest")
        manifest_dataset_name = manifest_payload.get("dataset_name")
        manifest_version = manifest_payload.get("version")
        if (
            isinstance(checkpoint_identity, dict)
            and manifest_dataset_name is not None
            and manifest_version is not None
        ):
            if checkpoint_identity.get("dataset_name") != manifest_dataset_name:
                raise InferenceCheckpointError(
                    "Checkpoint dataset_name does not match manifest dataset_name"
                )
            if checkpoint_identity.get("version") != manifest_version:
                raise InferenceCheckpointError(
                    "Checkpoint dataset_version does not match manifest version"
                )

    return InferenceContext(
        grid=grid,
        statistics=statistics,
        normalization=normalization,
        feature_shape=feature_shape,
        manifest_payload=manifest_payload,
    )
