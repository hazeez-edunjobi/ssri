"""Tests for Earth Engine sampleRectangle tiling / pixel-limit handling."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.data.feature_engineering import (
    CHANNEL_ORDER,
    EE_SAMPLE_MAX_TILE_SIDE,
    EE_SAMPLE_RECTANGLE_PIXEL_LIMIT,
    EE_SAMPLE_SAFE_PIXEL_LIMIT,
    FeatureStackError,
    _ee_sample_tile_plan,
    _export_ee_image_to_grid,
    _utm_window_to_wgs84_bbox,
    build_grid_spec_from_aoi,
)
from ssri_model.data.geophysics import GridSpec
from ssri_model.data.topography import RasterGrid


def _grid(width: int, height: int, *, epsg: int = 32631) -> GridSpec:
    return GridSpec(
        crs=rasterio.crs.CRS.from_epsg(epsg),
        transform=Affine(30.0, 0.0, 500_000.0, 0.0, -30.0, 720_000.0),
        width=width,
        height=height,
        nodata=-9999.0,
    )


class TestEeSampleTilePlan:
    def test_below_limit_uses_single_tile(self) -> None:
        grid = _grid(100, 100)  # 10_000 pixels
        tiles = _ee_sample_tile_plan(grid)
        assert tiles == [(0, 0, 100, 100)]
        assert grid.width * grid.height < EE_SAMPLE_SAFE_PIXEL_LIMIT

    def test_just_below_safe_limit_single_tile(self) -> None:
        # 500 * 500 = 250_000 == safe limit → still single tile
        grid = _grid(EE_SAMPLE_MAX_TILE_SIDE, EE_SAMPLE_MAX_TILE_SIDE)
        tiles = _ee_sample_tile_plan(grid)
        assert len(tiles) == 1
        assert tiles[0][2] * tiles[0][3] <= EE_SAMPLE_SAFE_PIXEL_LIMIT

    def test_above_limit_tiles_without_overlap_or_gaps(self) -> None:
        # ~314070-class size: 630 * 500 = 315_000
        width, height = 630, 500
        grid = _grid(width, height)
        assert width * height > EE_SAMPLE_SAFE_PIXEL_LIMIT
        tiles = _ee_sample_tile_plan(grid)
        assert len(tiles) >= 2
        covered = np.zeros((height, width), dtype=np.int32)
        for row_off, col_off, h, w in tiles:
            assert h * w <= EE_SAMPLE_MAX_TILE_SIDE**2
            assert h * w <= EE_SAMPLE_SAFE_PIXEL_LIMIT
            assert h * w <= EE_SAMPLE_RECTANGLE_PIXEL_LIMIT
            covered[row_off : row_off + h, col_off : col_off + w] += 1
        assert int(covered.min()) == 1
        assert int(covered.max()) == 1
        assert int(covered.sum()) == width * height

    def test_lagos_scale_aoi_tile_plan(self) -> None:
        # ~0.15 deg box around Lagos (~16.5 km) at 30 m ≈ 550^2 ≈ 302k pixels
        spec = build_grid_spec_from_aoi((3.30, 6.45, 3.45, 6.60), resolution_m=30.0)
        assert spec.width * spec.height > EE_SAMPLE_SAFE_PIXEL_LIMIT
        tiles = _ee_sample_tile_plan(spec)
        assert len(tiles) >= 2
        for _, _, h, w in tiles:
            assert h * w <= EE_SAMPLE_SAFE_PIXEL_LIMIT

    def test_rejects_absurdly_large_grid(self) -> None:
        grid = _grid(10_000, 10_000)
        with pytest.raises(FeatureStackError, match="too large"):
            _ee_sample_tile_plan(grid)


class TestUtmWindowBbox:
    def test_window_bbox_is_ordered(self) -> None:
        grid = _grid(100, 80)
        bbox = _utm_window_to_wgs84_bbox(grid, 10, 20, 30, 40)
        min_lon, min_lat, max_lon, max_lat = bbox
        assert min_lon < max_lon
        assert min_lat < max_lat


class TestExportEeImageTiled:
    def test_tiled_export_recombines_channels_aligned(self) -> None:
        grid = _grid(600, 400)  # 240k < safe? 240000 < 250000 — use larger
        grid = _grid(600, 500)  # 300_000 > safe
        tiles = _ee_sample_tile_plan(grid)
        assert len(tiles) >= 2

        def fake_sample(image, bbox, *, scale_m=30.0):
            # Return a small geographic array; alignment path is mocked below.
            data = np.ones((4, 4), dtype=np.float64) * 7.0
            return data, bbox

        def fake_align(source: RasterGrid, target: GridSpec) -> RasterGrid:
            data = np.full(target.shape, float(source.data.mean()), dtype=np.float64)
            return RasterGrid(
                data=data,
                transform=target.transform,
                crs=target.crs,
                nodata=target.nodata,
            )

        mock_image = MagicMock()
        with (
            patch(
                "ssri_model.data.feature_engineering._sample_ee_rectangle_array",
                side_effect=fake_sample,
            ),
            patch(
                "ssri_model.data.feature_engineering._align_raster_to_grid",
                side_effect=fake_align,
            ),
        ):
            result = _export_ee_image_to_grid(mock_image, grid, (3.3, 6.4, 3.5, 6.6))

        assert result.data.shape == (grid.height, grid.width)
        assert result.crs == grid.crs
        assert result.transform == grid.transform
        assert np.allclose(result.data, 7.0)
        # Channel contract still 13 names elsewhere
        assert len(CHANNEL_ORDER) == 13
