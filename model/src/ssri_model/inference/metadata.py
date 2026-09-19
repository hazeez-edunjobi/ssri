"""Manifest and inference metadata helpers."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Mapping

import rasterio
from rasterio.transform import Affine

from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES
from ssri_model.inference.exceptions import InferenceInputError


INFERENCE_JSON_NAME = "inference.json"


@dataclass(frozen=True)
class InferenceGrid:
    """Geospatial grid metadata for inference outputs."""

    crs: object
    transform: Affine
    width: int
    height: int
    resolution_m: float
    channel_names: tuple[str, ...]


def load_manifest_payload(path: Path | str) -> dict[str, Any]:
    """Load a JSON manifest document."""
    manifest_path = Path(path)
    if not manifest_path.exists():
        raise InferenceInputError(f"Manifest not found: {manifest_path}")
    return json.loads(manifest_path.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def _extract_channel_names(payload: Mapping[str, Any]) -> tuple[str, ...]:
    if "channels" in payload and isinstance(payload["channels"], list):
        names: list[str] = []
        for entry in payload["channels"]:
            if isinstance(entry, str):
                names.append(entry)
            elif isinstance(entry, Mapping) and "name" in entry:
                names.append(str(entry["name"]))
        if names:
            return tuple(names)
    if "channel_names" in payload:
        return tuple(str(name) for name in payload["channel_names"])
    return CHANNEL_NAMES


def read_inference_grid(manifest_path: Path | str) -> InferenceGrid:
    """Read geospatial grid metadata from a Stage 1 or dataset manifest."""
    payload = load_manifest_payload(manifest_path)
    channel_names = _extract_channel_names(payload)

    crs_value = payload.get("crs")
    if not crs_value:
        raise InferenceInputError("Manifest is missing CRS metadata")

    projection = payload.get("projection")
    if not isinstance(projection, Mapping):
        raise InferenceInputError("Manifest is missing projection metadata")

    transform_values = projection.get("transform")
    if not transform_values:
        raise InferenceInputError("Manifest projection.transform must contain 6 values")
    if len(transform_values) == 9:
        transform_values = transform_values[:6]
    if len(transform_values) != 6:
        raise InferenceInputError("Manifest projection.transform must contain 6 values")
    transform = Affine(*[float(value) for value in transform_values])

    width = projection.get("width")
    height = projection.get("height")
    tensor_shape = payload.get("tensor_shape")
    if (width is None or height is None) and isinstance(tensor_shape, list):
        if len(tensor_shape) == 3:
            height = tensor_shape[1]
            width = tensor_shape[2]
    if width is None or height is None:
        raise InferenceInputError("Manifest must define output width and height")

    resolution = payload.get("resolution_m")
    if resolution is None:
        raise InferenceInputError("Manifest is missing resolution_m")

    return InferenceGrid(
        crs=rasterio.crs.CRS.from_string(str(crs_value)),
        transform=transform,
        width=int(width),
        height=int(height),
        resolution_m=float(resolution),
        channel_names=channel_names,
    )


def validate_feature_shape(
    feature_shape: tuple[int, ...],
    grid: InferenceGrid,
) -> None:
    """Ensure feature tensor shape matches manifest dimensions."""
    if len(feature_shape) != 3:
        raise InferenceInputError(
            f"Feature stack must be 3D (C, H, W), received shape {feature_shape}"
        )
    channels, height, width = feature_shape
    if channels != CHANNEL_COUNT:
        raise InferenceInputError(
            f"Expected {CHANNEL_COUNT} channels, received {channels}"
        )
    if height != grid.height or width != grid.width:
        raise InferenceInputError(
            "Feature stack spatial dimensions do not match manifest; "
            f"expected ({grid.height}, {grid.width}), received ({height}, {width})"
        )


def write_inference_json(path: Path | str, payload: dict[str, Any]) -> Path:
    """Write inference metadata JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def build_inference_metadata(
    *,
    checkpoint_path: str,
    checkpoint_payload: Mapping[str, Any],
    feature_path: str,
    manifest_path: str,
    statistics_path: str,
    feature_shape: tuple[int, int, int],
    grid: InferenceGrid,
    config: Mapping[str, Any],
    outputs: Mapping[str, str],
    device: str,
    started_at: datetime,
    completed_at: datetime,
    elapsed_seconds: float,
) -> dict[str, Any]:
    """Build the inference.json document."""
    dataset_identity = checkpoint_payload.get("dataset_manifest") or {}
    return {
        "checkpoint": {
            "path": checkpoint_path,
            "dataset_name": dataset_identity.get("dataset_name"),
            "dataset_version": dataset_identity.get("version"),
            "model_config": checkpoint_payload.get("model_config"),
            "epoch": checkpoint_payload.get("epoch"),
            "best_metric": checkpoint_payload.get("best_metric"),
        },
        "input": {
            "feature_path": feature_path,
            "manifest_path": manifest_path,
            "statistics_path": statistics_path,
            "shape": list(feature_shape),
            "channels": list(CHANNEL_NAMES),
            "crs": str(grid.crs),
            "resolution_m": grid.resolution_m,
        },
        "inference": {
            **dict(config),
            "device": device,
            "timestamp": completed_at.isoformat(),
            "started_at": started_at.isoformat(),
            "completed_at": completed_at.isoformat(),
            "elapsed_seconds": elapsed_seconds,
        },
        "outputs": dict(outputs),
        "scientific_validation_status": "NOT_VALIDATED",
    }
