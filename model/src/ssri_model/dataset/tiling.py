"""Deterministic AOI tiling utilities for SSRI dataset generation."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from ssri_model.data.feature_engineering import (
    BoundingBox,
    build_grid_spec_from_aoi,
)
from ssri_model.data.geophysics import GridSpec
from rasterio.transform import xy
from rasterio.warp import transform_bounds


@dataclass(frozen=True)
class TilingConfig:
    """Configuration for deterministic AOI tiling."""

    tile_size_m: float
    overlap_m: float = 0.0
    id_prefix: str = "tile"

    def __post_init__(self) -> None:
        if self.tile_size_m <= 0:
            raise ValueError("tile_size_m must be greater than zero")
        if self.overlap_m < 0:
            raise ValueError("overlap_m must be non-negative")
        if self.overlap_m >= self.tile_size_m:
            raise ValueError("overlap_m must be less than tile_size_m")


@dataclass(frozen=True)
class TileSpec:
    """One reproducible tile derived from an AOI."""

    tile_id: str
    aoi: BoundingBox
    row: int
    col: int
    aoi_index: int = 0


def _window_to_wgs84_bbox(
    grid_spec: GridSpec,
    col_off: int,
    row_off: int,
    width: int,
    height: int,
) -> BoundingBox:
    """Convert a pixel window on the reference grid to a WGS84 bounding box."""
    west, north = xy(grid_spec.transform, row_off, col_off, offset="ul")
    east, south = xy(
        grid_spec.transform,
        row_off + height,
        col_off + width,
        offset="ul",
    )
    min_x = min(west, east)
    max_x = max(west, east)
    min_y = min(south, north)
    max_y = max(south, north)

    bounds = transform_bounds(
        grid_spec.crs,
        "EPSG:4326",
        min_x,
        min_y,
        max_x,
        max_y,
    )
    return (bounds[0], bounds[1], bounds[2], bounds[3])


def _deterministic_tile_id(
    *,
    prefix: str,
    aoi_index: int,
    row: int,
    col: int,
) -> str:
    """Build a stable tile identifier from grid coordinates."""
    return f"{prefix}-a{aoi_index:03d}-r{row:04d}-c{col:04d}"


def tile_aoi(
    aoi: BoundingBox,
    config: TilingConfig,
    *,
    resolution_m: float = 30.0,
    aoi_index: int = 0,
) -> list[TileSpec]:
    """Split an AOI into deterministic tiles.

    Args:
        aoi: WGS84 bounding box ``(min_lon, min_lat, max_lon, max_lat)``.
        config: Tiling configuration including tile size and overlap.
        resolution_m: Target raster resolution in meters.
        aoi_index: Index of the parent AOI for reproducible tile IDs.

    Returns:
        Ordered list of ``TileSpec`` instances covering the AOI.
    """
    grid_spec = build_grid_spec_from_aoi(aoi, resolution_m)
    tile_pixels = max(1, int(round(config.tile_size_m / resolution_m)))
    overlap_pixels = max(0, int(round(config.overlap_m / resolution_m)))
    step_pixels = max(1, tile_pixels - overlap_pixels)

    tiles: list[TileSpec] = []
    tile_row = 0
    for row_off in range(0, grid_spec.height, step_pixels):
        tile_col = 0
        for col_off in range(0, grid_spec.width, step_pixels):
            width = min(tile_pixels, grid_spec.width - col_off)
            height = min(tile_pixels, grid_spec.height - row_off)
            if width <= 0 or height <= 0:
                continue

            tile_bbox = _window_to_wgs84_bbox(
                grid_spec,
                col_off,
                row_off,
                width,
                height,
            )
            tile_id = _deterministic_tile_id(
                prefix=config.id_prefix,
                aoi_index=aoi_index,
                row=tile_row,
                col=tile_col,
            )
            tiles.append(
                TileSpec(
                    tile_id=tile_id,
                    aoi=tile_bbox,
                    row=tile_row,
                    col=tile_col,
                    aoi_index=aoi_index,
                )
            )
            tile_col += 1
        tile_row += 1

    if not tiles:
        digest = hashlib.sha1(repr(aoi).encode("utf-8")).hexdigest()[:8]
        tile_id = f"{config.id_prefix}-a{aoi_index:03d}-r0000-c0000-{digest}"
        tiles.append(
            TileSpec(
                tile_id=tile_id,
                aoi=aoi,
                row=0,
                col=0,
                aoi_index=aoi_index,
            )
        )

    return tiles


def tile_aois(
    aois: list[BoundingBox],
    config: TilingConfig,
    *,
    resolution_m: float = 30.0,
) -> list[TileSpec]:
    """Tile multiple AOIs into one deterministic tile list."""
    tiles: list[TileSpec] = []
    for index, aoi in enumerate(aois):
        tiles.extend(
            tile_aoi(
                aoi,
                config,
                resolution_m=resolution_m,
                aoi_index=index,
            )
        )
    return tiles
