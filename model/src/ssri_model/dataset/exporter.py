"""Sample export utilities for SSRI datasets."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import rasterio

from ssri_model.data.feature_engineering import FeatureStack
from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.ml.dataset_spec import FeatureSample
from ssri_model.ml.metadata import SampleMetadata
from ssri_model.dataset.exceptions import DatasetBuildError
from ssri_model.dataset.sample import feature_sample_from_paths


ELEVATION_INDEX = CHANNEL_NAMES.index("elevation")
NDVI_INDEX = CHANNEL_NAMES.index("ndvi")


def export_feature_stack(sample_dir: Path, stack: FeatureStack) -> Path:
    """Persist the feature tensor as ``feature_stack.npy``."""
    destination = sample_dir / "feature_stack.npy"
    return stack.save_numpy(destination)


def export_label_raster(
    sample_dir: Path,
    label: np.ndarray,
    stack: FeatureStack,
) -> Path:
    """Persist an aligned label raster as ``label.tif``."""
    destination = sample_dir / "label.tif"
    destination.parent.mkdir(parents=True, exist_ok=True)

    profile = {
        "driver": "GTiff",
        "height": stack.grid_spec.height,
        "width": stack.grid_spec.width,
        "count": 1,
        "dtype": label.dtype,
        "crs": stack.grid_spec.crs,
        "transform": stack.grid_spec.transform,
        "nodata": stack.grid_spec.nodata,
    }

    with rasterio.open(destination, "w", **profile) as dataset:
        dataset.write(label, 1)
        dataset.set_band_description(1, "label")

    return destination


def export_metadata(sample_dir: Path, metadata: SampleMetadata) -> Path:
    """Persist sample metadata as ``metadata.json``."""
    return metadata.save(sample_dir / "metadata.json")


def export_preview(
    sample_dir: Path,
    stack: FeatureStack,
    label: np.ndarray,
) -> Path:
    """Render a quick-look preview image for QA."""
    destination = sample_dir / "preview.png"
    destination.parent.mkdir(parents=True, exist_ok=True)

    elevation = stack.feature_tensor[ELEVATION_INDEX]
    ndvi = stack.feature_tensor[NDVI_INDEX]
    panels = [elevation, ndvi, label]
    titles = ["Elevation", "NDVI", "Label Mask"]

    figure, axes = plt.subplots(1, len(panels), figsize=(4 * len(panels), 4))
    if len(panels) == 1:
        axes = [axes]

    for axis, data, title in zip(axes, panels, titles, strict=True):
        image = axis.imshow(data, cmap="viridis")
        axis.set_title(title)
        axis.axis("off")
        figure.colorbar(image, ax=axis, fraction=0.046, pad=0.04)

    figure.tight_layout()
    try:
        figure.savefig(destination, dpi=120, bbox_inches="tight")
    except OSError as exc:
        plt.close(figure)
        raise DatasetBuildError(f"Failed to write preview image: {destination}") from exc
    finally:
        plt.close(figure)

    return destination


def export_sample(
    sample_dir: Path | str,
    *,
    stack: FeatureStack,
    metadata: SampleMetadata,
    label: np.ndarray | None = None,
) -> FeatureSample:
    """Export all required artifacts for one dataset sample."""
    directory = Path(sample_dir)
    directory.mkdir(parents=True, exist_ok=True)

    export_feature_stack(directory, stack)
    export_metadata(directory, metadata)

    label_array = label if label is not None else np.full(
        stack.grid_spec.shape,
        stack.grid_spec.nodata,
        dtype=np.float32,
    )
    export_preview(directory, stack, label_array)
    export_label_raster(directory, label_array, stack)

    return feature_sample_from_paths(
        sample_id=metadata.sample_id,
        sample_dir=directory,
        has_label=True,
    )
