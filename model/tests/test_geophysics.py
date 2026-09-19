"""Tests for the geophysics loading and alignment module."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine
from rasterio.warp import transform_bounds

from ssri_model.data.geophysics import (
    DEFAULT_NODATA,
    EIGEN6C4Provider,
    GeophysicsAlignmentError,
    GeophysicsConfig,
    GeophysicsConfigError,
    GeophysicsDataError,
    GridSpec,
    ProviderType,
    get_provider,
    load_gravity,
    load_magnetics,
    reproject_to_grid,
    resample_to_grid,
    validate_alignment,
)
from ssri_model.data.topography import RasterGrid


def _build_raster_grid(
    width: int = 10,
    height: int = 10,
    epsg: int = 32613,
    pixel_size: float = 30.0,
    origin_x: float = 500000.0,
    origin_y: float = 4100000.0,
    base_value: float = 10.0,
) -> RasterGrid:
    """Create a synthetic single-band raster grid."""
    transform = Affine(pixel_size, 0.0, origin_x, 0.0, -pixel_size, origin_y)
    crs = rasterio.crs.CRS.from_epsg(epsg)
    x = np.linspace(0.0, 1.0, width)
    y = np.linspace(0.0, 1.0, height)
    xv, yv = np.meshgrid(x, y)
    data = (base_value + xv + yv).astype(np.float64)
    return RasterGrid(data=data, transform=transform, crs=crs, nodata=DEFAULT_NODATA)


def _write_geotiff(path: Path, grid: RasterGrid) -> None:
    """Write a ``RasterGrid`` to GeoTIFF."""
    path.parent.mkdir(parents=True, exist_ok=True)
    profile = {
        "driver": "GTiff",
        "height": grid.height,
        "width": grid.width,
        "count": 1,
        "dtype": grid.data.dtype,
        "crs": grid.crs,
        "transform": grid.transform,
        "nodata": grid.nodata,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(grid.data, 1)


@pytest.fixture
def geo_config(tmp_path: Path) -> GeophysicsConfig:
    """Provide configured gravity and magnetic dataset paths."""
    gravity = _build_raster_grid(base_value=20.0)
    magnetic = _build_raster_grid(base_value=40.0)
    gravity_path = tmp_path / "gravity.tif"
    magnetic_path = tmp_path / "magnetic.tif"
    _write_geotiff(gravity_path, gravity)
    _write_geotiff(magnetic_path, magnetic)
    return GeophysicsConfig(
        gravity_data_path=gravity_path,
        magnetic_data_path=magnetic_path,
    )


@pytest.fixture
def target_grid() -> GridSpec:
    """Provide a higher-resolution target grid specification."""
    reference = _build_raster_grid(width=6, height=6, pixel_size=10.0)
    return GridSpec.from_raster_grid(reference)


class TestProviderSelection:
    def test_get_provider_returns_local_geotiff(self, geo_config: GeophysicsConfig) -> None:
        provider = get_provider(ProviderType.LOCAL_GEOTIFF, config=geo_config)
        assert isinstance(provider, EIGEN6C4Provider)

    def test_load_gravity_uses_default_provider(
        self,
        geo_config: GeophysicsConfig,
    ) -> None:
        with patch(
            "ssri_model.data.geophysics.get_provider",
            return_value=EIGEN6C4Provider(config=geo_config),
        ) as mock_get_provider:
            load_gravity(
                (-1.0, 50.0, 1.0, 52.0),
                config=geo_config,
            )

        mock_get_provider.assert_called_once()


def _wgs84_bounds_for_grid(grid: RasterGrid) -> tuple[float, float, float, float]:
    """Convert a raster extent to a WGS84 bounding box."""
    left = grid.transform.c
    top = grid.transform.f
    right = left + grid.transform.a * grid.width
    bottom = top + grid.transform.e * grid.height
    west, south, east, north = transform_bounds(
        grid.crs,
        "EPSG:4326",
        left,
        bottom,
        right,
        top,
    )
    return (west, south, east, north)


class TestProviderLoading:
    def test_load_gravity_from_local_geotiff(
        self,
        geo_config: GeophysicsConfig,
    ) -> None:
        provider = EIGEN6C4Provider(config=geo_config)
        reference = _build_raster_grid(base_value=20.0)
        aoi = _wgs84_bounds_for_grid(reference)
        grid = provider.load_gravity(aoi)

        assert grid.width > 0
        assert grid.height > 0
        assert grid.crs.to_epsg() == 32613

    def test_load_magnetics_from_local_geotiff(
        self,
        geo_config: GeophysicsConfig,
    ) -> None:
        provider = EIGEN6C4Provider(config=geo_config)
        reference = _build_raster_grid(base_value=40.0)
        aoi = _wgs84_bounds_for_grid(reference)
        grid = provider.load_magnetics(aoi)

        assert grid.width > 0
        assert grid.height > 0
        assert np.nanmean(grid.data) > 40.0

    def test_load_gravity_raises_when_path_missing(
        self,
        tmp_path: Path,
    ) -> None:
        config = GeophysicsConfig(
            gravity_data_path=tmp_path / "missing_gravity.tif",
            magnetic_data_path=None,
        )
        provider = EIGEN6C4Provider(config=config)

        with pytest.raises(GeophysicsDataError, match="unavailable|not found"):
            provider.load_gravity((-1.0, 50.0, 1.0, 52.0))

    def test_load_gravity_raises_when_env_not_configured(self) -> None:
        config = GeophysicsConfig(gravity_data_path=None, magnetic_data_path=None)
        provider = EIGEN6C4Provider(config=config)

        with pytest.raises(GeophysicsConfigError, match="GRAVITY_DATA_PATH"):
            provider.load_gravity((-1.0, 50.0, 1.0, 52.0))

    def test_load_magnetics_raises_when_env_not_configured(self) -> None:
        config = GeophysicsConfig(gravity_data_path=None, magnetic_data_path=None)
        provider = EIGEN6C4Provider(config=config)

        with pytest.raises(GeophysicsConfigError, match="MAGNETIC_DATA_PATH"):
            provider.load_magnetics((-1.0, 50.0, 1.0, 52.0))

    def test_provider_aligns_to_target_grid(
        self,
        geo_config: GeophysicsConfig,
        target_grid: GridSpec,
    ) -> None:
        provider = EIGEN6C4Provider(config=geo_config)
        reference = _build_raster_grid(base_value=20.0)
        aoi = _wgs84_bounds_for_grid(reference)
        grid = provider.load_gravity(aoi, target_grid=target_grid)

        validate_alignment(target_grid, grid)

    def test_subpixel_aoi_still_loads_and_reprojects(
        self,
        tmp_path: Path,
    ) -> None:
        """AOI smaller than one native geophysics cell must not yield 0x0 reads."""
        from ssri_model.data.feature_engineering import build_grid_spec_from_aoi
        from ssri_model.data.geophysics import LocalGeoTIFFProvider

        # Coarse geographic grid similar to Lagos WGM2012 clips (~0.03 deg).
        transform = Affine(0.03, 0.0, 2.5, 0.0, -0.03, 7.5)
        crs = rasterio.crs.CRS.from_epsg(4326)
        data = np.linspace(10.0, 20.0, 60 * 60, dtype=np.float64).reshape(60, 60)
        grid = RasterGrid(data=data, transform=transform, crs=crs, nodata=DEFAULT_NODATA)
        gravity_path = tmp_path / "coarse_gravity.tif"
        _write_geotiff(gravity_path, grid)

        provider = LocalGeoTIFFProvider(
            config=GeophysicsConfig(
                gravity_data_path=gravity_path,
                magnetic_data_path=None,
            )
        )
        # ~0.002 deg box << one 0.03 deg cell (dashboard tiny polygons / buffers).
        tiny_aoi = (3.379, 6.519, 3.381, 6.521)
        loaded = provider.load_gravity(tiny_aoi)
        assert loaded.data.size > 0
        assert min(loaded.data.shape) >= 1

        target = build_grid_spec_from_aoi(tiny_aoi, resolution_m=30.0)
        aligned = provider.load_gravity(tiny_aoi, target_grid=target)
        validate_alignment(target, aligned)


class TestGridOperations:
    def test_resample_to_grid_preserves_crs_and_shape(self) -> None:
        source = _build_raster_grid(width=10, height=10, pixel_size=30.0)
        target = GridSpec.from_raster_grid(
            _build_raster_grid(width=6, height=6, pixel_size=10.0)
        )

        resampled = resample_to_grid(source, target)

        assert resampled.shape == target.shape
        assert resampled.crs == target.crs
        assert resampled.transform == target.transform

    def test_resample_to_grid_rejects_crs_mismatch(self) -> None:
        source = _build_raster_grid(epsg=32613)
        target = GridSpec.from_raster_grid(_build_raster_grid(epsg=32614))

        with pytest.raises(GeophysicsAlignmentError, match="CRS mismatch"):
            resample_to_grid(source, target)

    def test_reproject_to_grid_changes_crs_and_shape(self) -> None:
        source = _build_raster_grid(width=8, height=8, epsg=32613, pixel_size=30.0)
        target = GridSpec.from_raster_grid(
            _build_raster_grid(width=5, height=5, epsg=32614, pixel_size=20.0)
        )

        reprojected = reproject_to_grid(source, target)

        assert reprojected.shape == target.shape
        assert reprojected.crs == target.crs
        assert reprojected.transform == target.transform

    def test_validate_alignment_detects_shape_mismatch(self) -> None:
        reference = GridSpec.from_raster_grid(_build_raster_grid(width=5, height=5))
        candidate = _build_raster_grid(width=4, height=4)

        with pytest.raises(GeophysicsAlignmentError, match="Shape mismatch"):
            validate_alignment(reference, candidate)

    def test_resampled_grid_has_no_unexpected_nan(self) -> None:
        source = _build_raster_grid()
        target = GridSpec.from_raster_grid(_build_raster_grid(width=4, height=4))
        resampled = resample_to_grid(source, target)

        assert not np.any(np.isnan(resampled.data))


class TestModuleFunctions:
    def test_load_gravity_with_explicit_provider(
        self,
        geo_config: GeophysicsConfig,
    ) -> None:
        provider = EIGEN6C4Provider(config=geo_config)
        reference = _build_raster_grid(base_value=20.0)
        aoi = _wgs84_bounds_for_grid(reference)
        grid = load_gravity(aoi, provider=provider)

        assert isinstance(grid, RasterGrid)

    def test_load_magnetics_with_explicit_provider(
        self,
        geo_config: GeophysicsConfig,
    ) -> None:
        provider = EIGEN6C4Provider(config=geo_config)
        reference = _build_raster_grid(base_value=40.0)
        aoi = _wgs84_bounds_for_grid(reference)
        grid = load_magnetics(aoi, provider=provider)

        assert isinstance(grid, RasterGrid)


class TestGeometryInput:
    def test_resolve_bounds_from_ee_geometry(self) -> None:
        class FakeGeometry:
            """Stand-in for ``ee.Geometry``."""

        geometry = FakeGeometry()
        geometry.bounds = MagicMock(
            return_value=MagicMock(
                getInfo=MagicMock(
                    return_value={
                        "coordinates": [
                            [
                                [-1.0, 50.0],
                                [1.0, 50.0],
                                [1.0, 52.0],
                                [-1.0, 52.0],
                                [-1.0, 50.0],
                            ]
                        ]
                    }
                )
            )
        )

        mock_ee = MagicMock()
        mock_ee.Geometry = FakeGeometry

        provider = EIGEN6C4Provider(
            config=GeophysicsConfig(
                gravity_data_path=Path("unused.tif"),
                magnetic_data_path=None,
            )
        )

        with patch.dict(sys.modules, {"ee": mock_ee}):
            with patch(
                "ssri_model.data.geophysics._load_geotiff_for_aoi",
                return_value=_build_raster_grid(),
            ) as mock_load:
                provider.load_gravity(geometry)

        mock_load.assert_called_once()
