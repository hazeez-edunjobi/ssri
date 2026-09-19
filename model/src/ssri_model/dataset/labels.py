"""Label provider abstractions for SSRI dataset generation."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Mapping

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.warp import reproject

from ssri_model.data.geophysics import GridSpec
from ssri_model.dataset.exceptions import DatasetError, MissingValueError


class LabelProviderError(DatasetError):
    """Base exception for label provider failures."""


class LabelNotFoundError(LabelProviderError):
    """Raised when a label raster cannot be located."""


class LabelProvider(ABC):
    """Abstract interface for hazard label sources."""

    @abstractmethod
    def load_label(
        self,
        tile_id: str,
        target_grid: GridSpec,
    ) -> np.ndarray:
        """Load and align a label raster for a tile."""


class LocalRasterLabelProvider(LabelProvider):
    """Load per-tile label rasters from a local directory."""

    def __init__(
        self,
        label_dir: Path | str,
        *,
        filename_template: str = "{tile_id}.tif",
        nodata: float | None = None,
    ) -> None:
        self.label_dir = Path(label_dir)
        self.filename_template = filename_template
        self.nodata = nodata

    def resolve_path(self, tile_id: str) -> Path:
        """Resolve the on-disk label path for a tile identifier."""
        return self.label_dir / self.filename_template.format(tile_id=tile_id)

    def load_label(
        self,
        tile_id: str,
        target_grid: GridSpec,
    ) -> np.ndarray:
        """Load a local GeoTIFF label and reproject it to the target grid."""
        path = self.resolve_path(tile_id)
        if not path.exists():
            raise LabelNotFoundError(f"Label raster not found for tile '{tile_id}': {path}")

        destination = np.full(target_grid.shape, target_grid.nodata, dtype=np.float32)

        with rasterio.open(path) as source:
            reproject(
                source=rasterio.band(source, 1),
                destination=destination,
                src_transform=source.transform,
                src_crs=source.crs,
                dst_transform=target_grid.transform,
                dst_crs=target_grid.crs,
                resampling=Resampling.nearest,
                src_nodata=source.nodata if source.nodata is not None else self.nodata,
                dst_nodata=target_grid.nodata,
            )

        return destination


class PolygonLabelProvider(LabelProvider):
    """Placeholder for future polygon-based label rasterization."""

    def __init__(self, labels: Mapping[str, Path | str]) -> None:
        self.labels = {key: Path(value) for key, value in labels.items()}

    def load_label(
        self,
        tile_id: str,
        target_grid: GridSpec,
    ) -> np.ndarray:
        raise NotImplementedError(
            "PolygonLabelProvider is reserved for a future release"
        )


class RemoteLabelProvider(LabelProvider):
    """Placeholder for future remote label providers."""

    def load_label(
        self,
        tile_id: str,
        target_grid: GridSpec,
    ) -> np.ndarray:
        raise NotImplementedError(
            "RemoteLabelProvider is reserved for a future release"
        )


def require_label(label: np.ndarray | None, *, tile_id: str) -> np.ndarray:
    """Ensure a label array is present."""
    if label is None:
        raise MissingValueError(f"Missing label raster for tile '{tile_id}'")
    return label
