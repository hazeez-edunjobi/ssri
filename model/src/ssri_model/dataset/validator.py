"""Dataset validation utilities."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio

from ssri_model.ml.constants import CHANNEL_COUNT
from ssri_model.ml.metadata import SampleMetadata
from ssri_model.dataset.exceptions import (
    ChannelCountError,
    CorruptFileError,
    CRSError,
    LabelDimensionError,
    MetadataIncompleteError,
    MissingValueError,
    TensorShapeError,
)


REQUIRED_METADATA_FIELDS = (
    "sample_id",
    "aoi",
    "acquisition",
    "resolution_m",
    "crs",
    "sources",
    "package_version",
    "created_at",
)

REQUIRED_SAMPLE_FILES = (
    "feature_stack.npy",
    "label.tif",
    "metadata.json",
    "preview.png",
)


def validate_metadata(metadata: SampleMetadata) -> None:
    """Validate that sample metadata contains required fields."""
    payload = metadata.to_dict()
    missing = [field for field in REQUIRED_METADATA_FIELDS if not payload.get(field)]
    if missing:
        raise MetadataIncompleteError(
            f"Sample '{metadata.sample_id}' metadata missing fields: {', '.join(missing)}"
        )
    if not metadata.crs:
        raise CRSError(f"Sample '{metadata.sample_id}' is missing CRS metadata")


def validate_feature_tensor(
    tensor: np.ndarray,
    *,
    sample_id: str,
) -> tuple[int, int]:
    """Validate feature tensor rank, channel count, and spatial dimensions."""
    if tensor.ndim != 3:
        raise TensorShapeError(
            f"Sample '{sample_id}' feature tensor must be 3D, received shape {tensor.shape}"
        )

    channels, height, width = tensor.shape
    if channels != CHANNEL_COUNT:
        raise ChannelCountError(
            f"Sample '{sample_id}' expected {CHANNEL_COUNT} channels, received {channels}"
        )
    if height <= 0 or width <= 0:
        raise TensorShapeError(
            f"Sample '{sample_id}' has invalid spatial dimensions: {height}x{width}"
        )

    if not np.isfinite(tensor).all():
        raise MissingValueError(
            f"Sample '{sample_id}' feature tensor contains non-finite values"
        )

    return height, width


def validate_label_raster(
    label_path: Path,
    *,
    sample_id: str,
    expected_shape: tuple[int, int],
    expected_crs: str,
) -> None:
    """Validate label raster dimensions and CRS."""
    try:
        with rasterio.open(label_path) as dataset:
            if dataset.count < 1:
                raise CorruptFileError(
                    f"Sample '{sample_id}' label raster has no bands: {label_path}"
                )
            if (dataset.height, dataset.width) != expected_shape:
                raise LabelDimensionError(
                    f"Sample '{sample_id}' label shape "
                    f"{dataset.height}x{dataset.width} != feature shape "
                    f"{expected_shape[0]}x{expected_shape[1]}"
                )
            if str(dataset.crs) != expected_crs:
                raise CRSError(
                    f"Sample '{sample_id}' label CRS '{dataset.crs}' "
                    f"does not match metadata CRS '{expected_crs}'"
                )
    except rasterio.errors.RasterioIOError as exc:
        raise CorruptFileError(
            f"Unable to read label raster for sample '{sample_id}': {label_path}"
        ) from exc


def validate_sample_directory(sample_dir: Path | str) -> SampleMetadata:
    """Validate one exported sample directory."""
    directory = Path(sample_dir)
    sample_id = directory.name

    for filename in REQUIRED_SAMPLE_FILES:
        path = directory / filename
        if not path.exists():
            raise MissingValueError(
                f"Sample '{sample_id}' is missing required file: {filename}"
            )

    metadata_path = directory / "metadata.json"
    try:
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CorruptFileError(
            f"Unable to read metadata for sample '{sample_id}'"
        ) from exc

    missing = [
        field
        for field in REQUIRED_METADATA_FIELDS
        if field not in payload or payload[field] in (None, "")
    ]
    if missing:
        raise MetadataIncompleteError(
            f"Sample '{sample_id}' metadata missing fields: {', '.join(missing)}"
        )

    try:
        metadata = SampleMetadata.from_dict(payload)
    except (KeyError, TypeError, ValueError) as exc:
        raise CorruptFileError(
            f"Unable to parse metadata for sample '{sample_id}'"
        ) from exc

    validate_metadata(metadata)

    try:
        tensor = np.load(directory / "feature_stack.npy")
    except (OSError, ValueError) as exc:
        raise CorruptFileError(
            f"Unable to read feature tensor for sample '{sample_id}'"
        ) from exc

    height, width = validate_feature_tensor(tensor, sample_id=metadata.sample_id)

    label_path = directory / "label.tif"
    validate_label_raster(
        label_path,
        sample_id=metadata.sample_id,
        expected_shape=(height, width),
        expected_crs=metadata.crs,
    )

    preview_path = directory / "preview.png"
    if preview_path.stat().st_size == 0:
        raise CorruptFileError(
            f"Sample '{sample_id}' preview image is empty: {preview_path}"
        )

    return metadata


def validate_dataset_root(dataset_root: Path | str) -> None:
    """Validate all split directories under a dataset root."""
    root = Path(dataset_root)
    for split in ("train", "validation", "test"):
        split_dir = root / split
        if not split_dir.exists():
            continue
        for sample_dir in sorted(path for path in split_dir.iterdir() if path.is_dir()):
            validate_sample_directory(sample_dir)
