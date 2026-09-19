"""Geospatial prediction raster writers for SSRI inference."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import rasterio

from ssri_model.ml.constants import LABEL_NODATA
from ssri_model.inference.exceptions import InferenceAlignmentError
from ssri_model.inference.metadata import InferenceGrid


def _validate_shape(array_shape: tuple[int, ...], grid: InferenceGrid) -> None:
    if len(array_shape) == 2:
        height, width = array_shape
    elif len(array_shape) == 3:
        _, height, width = array_shape
    else:
        raise InferenceAlignmentError(
            f"Unsupported array shape for raster export: {array_shape}"
        )
    if height != grid.height or width != grid.width:
        raise InferenceAlignmentError(
            "Output shape does not match manifest grid; "
            f"expected ({grid.height}, {grid.width}), received ({height}, {width})"
        )


def save_prediction_raster(
    path: Path | str,
    prediction: np.ndarray,
    *,
    grid: InferenceGrid,
) -> Path:
    """Write a single-band class prediction GeoTIFF."""
    _validate_shape(prediction.shape, grid)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": "int16",
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": LABEL_NODATA,
    }
    with rasterio.open(destination, "w", **profile) as dataset:
        dataset.write(prediction.astype(np.int16), 1)
    return destination


def save_confidence_raster(
    path: Path | str,
    confidence: np.ndarray,
    *,
    grid: InferenceGrid,
) -> Path:
    """Write a single-band confidence GeoTIFF."""
    _validate_shape(confidence.shape, grid)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": "float32",
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": 0.0,
    }
    with rasterio.open(destination, "w", **profile) as dataset:
        dataset.write(confidence.astype(np.float32), 1)
    return destination


def save_probability_raster(
    path: Path | str,
    probabilities: np.ndarray,
    *,
    grid: InferenceGrid,
) -> Path:
    """Write a three-band probability GeoTIFF."""
    if probabilities.shape != (3, grid.height, grid.width):
        raise InferenceAlignmentError(
            "Probability array must have shape (3, H, W); "
            f"received {probabilities.shape}"
        )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 3,
        "dtype": "float32",
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": 0.0,
    }
    descriptions = (
        "subsidence_probability",
        "landslide_probability",
        "sinkhole_probability",
    )
    with rasterio.open(destination, "w", **profile) as dataset:
        for band in range(3):
            dataset.set_band_description(band + 1, descriptions[band])
            dataset.write(probabilities[band].astype(np.float32), band + 1)
    return destination


def save_class_probability_raster(
    path: Path | str,
    probabilities: np.ndarray,
    *,
    grid: InferenceGrid,
    description: str,
) -> Path:
    """Write a single-band class probability GeoTIFF."""
    _validate_shape(probabilities.shape, grid)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": "float32",
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": 0.0,
    }
    with rasterio.open(destination, "w", **profile) as dataset:
        dataset.set_band_description(1, description)
        dataset.write(probabilities.astype(np.float32), 1)
    return destination
