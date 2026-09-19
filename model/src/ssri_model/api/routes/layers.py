"""Read-only map layer endpoints for frontend visualization.

Does not alter FeatureStack or geophysics acquisition. Serves already-validated
local GeoTIFF products as GeoJSON for MapLibre (EPSG:4326 lon/lat).
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from rasterio.transform import xy

router = APIRouter(tags=["layers"])

DEFAULT_GRAVITY = "/data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif"
DEFAULT_MAGNETIC = "/data/geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif"


class LayerMetadata(BaseModel):
    layer_id: str
    title: str
    dataset: str
    provider: str
    units: str
    native_resolution: str
    crs: str
    nodata: float | None
    value_min: float | None
    value_max: float | None
    feature_count: int
    scientific_limitation: str
    source_path_basename: str


class GravityLayerResponse(BaseModel):
    type: str = "FeatureCollection"
    features: list[dict[str, Any]] = Field(default_factory=list)
    metadata: LayerMetadata


def _resolve_path(env_name: str, default: str) -> Path:
    raw = os.getenv(env_name) or default
    path = Path(raw)
    if path.is_file():
        return path
    # model/src/ssri_model/api/routes/layers.py → repo root is parents[5]
    repo = Path(__file__).resolve().parents[5]
    alt = repo / "data" / "geophysics" / "processed" / path.name
    if alt.is_file():
        return alt
    relative = repo / raw
    if relative.is_file():
        return relative
    return path


def _raster_to_geojson(
    path: Path,
    *,
    max_cells: int,
) -> tuple[list[dict[str, Any]], float | None, float | None, float | None]:
    with rasterio.open(path) as dataset:
        if dataset.count < 1:
            raise HTTPException(status_code=500, detail="Raster has no bands")
        data = dataset.read(1).astype(np.float64)
        nodata = float(dataset.nodata) if dataset.nodata is not None else None
        transform = dataset.transform
        height, width = data.shape

        # Ensure we emit geographic lon/lat for MapLibre.
        if dataset.crs is not None and dataset.crs.to_epsg() not in {4326, None}:
            # Reproject bounds sampling would be heavier; qualification rasters are 4326.
            if "4326" not in dataset.crs.to_string():
                raise HTTPException(
                    status_code=500,
                    detail=(
                        f"Gravity preview requires EPSG:4326 GeoTIFF; got {dataset.crs}"
                    ),
                )

        mask = ~np.isfinite(data)
        if nodata is not None:
            mask |= np.isclose(data, nodata)

        valid_idx = np.argwhere(~mask)
        if valid_idx.size == 0:
            raise HTTPException(status_code=404, detail="Raster contains only nodata")

        step = 1
        n_valid = int(valid_idx.shape[0])
        if n_valid > max_cells:
            step = int(np.ceil(np.sqrt(n_valid / max_cells)))

        features: list[dict[str, Any]] = []
        values: list[float] = []
        for row in range(0, height, step):
            for col in range(0, width, step):
                if mask[row, col]:
                    continue
                # Pixel corners in geographic CRS (north-up: transform.e < 0).
                x0, y0 = xy(transform, row + 0.5, col + 0.5, offset="ul")
                x1, y1 = xy(transform, row + step - 0.5, col + step - 0.5, offset="lr")
                west, east = (float(x0), float(x1)) if x0 <= x1 else (float(x1), float(x0))
                south, north = (float(y1), float(y0)) if y1 <= y0 else (float(y0), float(y1))
                value = float(data[row, col])
                values.append(value)
                features.append(
                    {
                        "type": "Feature",
                        "properties": {"value": value},
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [
                                [
                                    [west, south],
                                    [east, south],
                                    [east, north],
                                    [west, north],
                                    [west, south],
                                ]
                            ],
                        },
                    }
                )

        vmin = float(np.min(values)) if values else None
        vmax = float(np.max(values)) if values else None
        return features, vmin, vmax, nodata


@router.get("/layers/gravity", response_model=GravityLayerResponse)
def get_gravity_layer(
    max_cells: int = Query(default=2500, ge=100, le=20000),
) -> GravityLayerResponse:
    """Return WGM2012 Bouguer anomaly cells as GeoJSON for MapLibre."""
    path = _resolve_path("GRAVITY_DATA_PATH", DEFAULT_GRAVITY)
    if not path.is_file():
        raise HTTPException(
            status_code=404,
            detail="GRAVITY_DATA_PATH GeoTIFF not found for visualization",
        )

    features, vmin, vmax, nodata = _raster_to_geojson(path, max_cells=max_cells)
    return GravityLayerResponse(
        features=features,
        metadata=LayerMetadata(
            layer_id="gravity",
            title="WGM2012 Complete Spherical Bouguer anomaly",
            dataset="WGM2012 Complete Spherical Bouguer anomaly",
            provider="Bureau Gravimétrique International (BGI)",
            units="mGal",
            native_resolution="approximately 2 arc-minutes (regional)",
            crs="EPSG:4326",
            nodata=nodata,
            value_min=vmin,
            value_max=vmax,
            feature_count=len(features),
            scientific_limitation=(
                "Regional ~2' grid. Display cells are downsampled for the map; "
                "this is not 30 m native geophysical resolution."
            ),
            source_path_basename=path.name,
        ),
    )
