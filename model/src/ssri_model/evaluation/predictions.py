"""Prediction artifact writers for SSRI evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import rasterio
import torch
import torch.nn.functional as F

from ssri_model.ml.constants import FEATURE_NODATA, LABEL_NODATA
from ssri_model.evaluation.exceptions import PredictionAlignmentError


@dataclass(frozen=True)
class RasterGrid:
    """Geospatial grid metadata for aligned prediction outputs."""

    crs: object
    transform: rasterio.Affine
    width: int
    height: int
    nodata: float = FEATURE_NODATA


def read_label_grid(label_path: Path | str) -> RasterGrid:
    """Read geospatial grid metadata from a source label raster."""
    path = Path(label_path)
    with rasterio.open(path) as dataset:
        return RasterGrid(
            crs=dataset.crs,
            transform=dataset.transform,
            width=int(dataset.width),
            height=int(dataset.height),
            nodata=float(dataset.nodata if dataset.nodata is not None else FEATURE_NODATA),
        )


def validate_prediction_alignment(
    array_shape: tuple[int, int],
    grid: RasterGrid,
) -> None:
    """Ensure a prediction array matches the source raster grid."""
    height, width = array_shape
    if height != grid.height or width != grid.width:
        raise PredictionAlignmentError(
            "Prediction shape does not match source grid; "
            f"expected ({grid.height}, {grid.width}), received ({height}, {width})"
        )


def logits_to_probabilities(logits: torch.Tensor) -> torch.Tensor:
    """Convert raw logits to per-class softmax probabilities."""
    return F.softmax(logits, dim=1)


def logits_to_predictions(logits: torch.Tensor) -> torch.Tensor:
    """Convert raw logits to integer class predictions."""
    return logits.argmax(dim=1)


def logits_to_confidence(logits: torch.Tensor) -> torch.Tensor:
    """Return maximum softmax probability per pixel."""
    probabilities = logits_to_probabilities(logits)
    return probabilities.max(dim=1).values


def _masked_prediction_array(
    predictions: torch.Tensor,
    valid_mask: torch.Tensor,
) -> np.ndarray:
    array = predictions.detach().cpu().numpy().astype(np.int16)
    output = np.full(array.shape, LABEL_NODATA, dtype=np.int16)
    output[valid_mask.detach().cpu().numpy()] = array[valid_mask.detach().cpu().numpy()]
    return output


def save_prediction_raster(
    path: Path | str,
    predictions: torch.Tensor,
    *,
    valid_mask: torch.Tensor,
    grid: RasterGrid,
) -> Path:
    """Write a single-band prediction GeoTIFF aligned to the source grid."""
    if predictions.ndim != 2:
        raise PredictionAlignmentError(
            f"Expected 2D prediction tensor, received ndim={predictions.ndim}"
        )
    validate_prediction_alignment((int(predictions.shape[0]), int(predictions.shape[1])), grid)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = _masked_prediction_array(predictions, valid_mask)

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
        dataset.write(data, 1)
    return destination


def save_confidence_raster(
    path: Path | str,
    confidence: torch.Tensor,
    *,
    valid_mask: torch.Tensor,
    grid: RasterGrid,
) -> Path:
    """Write a single-band confidence GeoTIFF."""
    if confidence.ndim != 2:
        raise PredictionAlignmentError(
            f"Expected 2D confidence tensor, received ndim={confidence.ndim}"
        )
    validate_prediction_alignment((int(confidence.shape[0]), int(confidence.shape[1])), grid)
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    array = confidence.detach().cpu().numpy().astype(np.float32)
    output = np.full(array.shape, grid.nodata, dtype=np.float32)
    output[valid_mask.detach().cpu().numpy()] = array[valid_mask.detach().cpu().numpy()]

    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": "float32",
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": grid.nodata,
    }
    with rasterio.open(destination, "w", **profile) as dataset:
        dataset.write(output, 1)
    return destination


def save_probability_raster(
    path: Path | str,
    probabilities: torch.Tensor,
    *,
    valid_mask: torch.Tensor,
    grid: RasterGrid,
) -> Path:
    """Write a three-band probability GeoTIFF (subsidence, landslide, sinkhole)."""
    if probabilities.ndim != 3 or probabilities.shape[0] != 3:
        raise PredictionAlignmentError(
            "Expected probability tensor shape (3, H, W), "
            f"received {tuple(probabilities.shape)}"
        )
    validate_prediction_alignment(
        (int(probabilities.shape[1]), int(probabilities.shape[2])),
        grid,
    )
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    array = probabilities.detach().cpu().numpy().astype(np.float32)
    output = np.full(array.shape, grid.nodata, dtype=np.float32)
    valid = valid_mask.detach().cpu().numpy()
    for band in range(3):
        band_data = array[band]
        masked = np.full(band_data.shape, grid.nodata, dtype=np.float32)
        masked[valid] = band_data[valid]
        output[band] = masked

    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 3,
        "dtype": "float32",
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": grid.nodata,
    }
    with rasterio.open(destination, "w", **profile) as dataset:
        for band in range(3):
            dataset.write(output[band], band + 1)
    return destination
