"""Assessment GeoTIFF helpers."""

from __future__ import annotations

from pathlib import Path

import numpy as np


def write_probability_geotiff(
    path: Path | str,
    array: np.ndarray,
    *,
    transform: tuple[float, float, float, float, float, float] | None = None,
    crs: str = "EPSG:4326",
    nodata: float = -9999.0,
) -> Path:
    """Write a single-band float32 GeoTIFF probability raster."""
    try:
        import rasterio
        from rasterio.transform import from_origin
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("rasterio is required to write GeoTIFF outputs") from exc

    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    data = np.asarray(array, dtype=np.float32)
    if data.ndim != 2:
        raise ValueError("array must be 2D (H, W)")
    height, width = data.shape
    affine = (
        from_origin(0.0, float(height), 1.0, 1.0)
        if transform is None
        else rasterio.Affine(*transform)
    )
    with rasterio.open(
        destination,
        "w",
        driver="GTiff",
        height=height,
        width=width,
        count=1,
        dtype="float32",
        crs=crs,
        transform=affine,
        nodata=nodata,
        compress="deflate",
    ) as dataset:
        dataset.write(data, 1)
    return destination
