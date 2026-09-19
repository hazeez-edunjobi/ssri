"""Tests for the topography retrieval and terrain derivative module."""

from __future__ import annotations

import io
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.data.topography import (
    DEFAULT_NODATA,
    DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M,
    DEMType,
    RasterGrid,
    TopographyConfig,
    TopographyConfigError,
    TopographyDownloadError,
    TopographyProcessingError,
    _bbox_side_lengths_m,
    _resolve_bounds,
    _validate_grid_alignment,
    _write_geotiff,
    compute_profile_curvature,
    compute_plan_curvature,
    compute_relative_relief,
    compute_slope,
    compute_twi,
    compute_valley_depth,
    download_dem,
    ensure_min_bbox_side_m,
    load_dem,
)


def _build_synthetic_grid(
    width: int = 20,
    height: int = 20,
    nodata_fraction: float = 0.0,
) -> RasterGrid:
    """Create a sloping synthetic DEM grid for derivative tests."""
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    crs = rasterio.crs.CRS.from_epsg(32613)
    x = np.linspace(0.0, 4.0, width)
    y = np.linspace(0.0, 4.0, height)
    xv, yv = np.meshgrid(x, y)
    data = (100.0 + xv * 2.0 + yv * 3.0).astype(np.float64)

    if nodata_fraction > 0:
        rng = np.random.default_rng(42)
        invalid_count = int(width * height * nodata_fraction)
        flat_indices = rng.choice(width * height, size=invalid_count, replace=False)
        data.ravel()[flat_indices] = DEFAULT_NODATA

    return RasterGrid(
        data=data,
        transform=transform,
        crs=crs,
        nodata=DEFAULT_NODATA,
    )


def _grid_to_geotiff_bytes(grid: RasterGrid) -> bytes:
    """Serialize a ``RasterGrid`` to GeoTIFF bytes."""
    buffer = io.BytesIO()
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
    with rasterio.open(buffer, "w", **profile) as dataset:
        dataset.write(grid.data, 1)
    return buffer.getvalue()


@pytest.fixture
def topo_config() -> TopographyConfig:
    """Provide a valid OpenTopography configuration."""
    return TopographyConfig(api_key="test-opentopography-key")


@pytest.fixture
def synthetic_dem(tmp_path: Path) -> tuple[RasterGrid, Path]:
    """Provide a synthetic DEM grid and on-disk GeoTIFF."""
    grid = _build_synthetic_grid()
    dem_path = tmp_path / "dem.tif"
    _write_geotiff(grid, dem_path)
    return grid, dem_path


class TestConfiguration:
    def test_from_env_raises_when_api_key_missing(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(
                TopographyConfigError,
                match="OPENTOPOGRAPHY_API_KEY",
            ):
                TopographyConfig.from_env()

    def test_from_env_rejects_whitespace_only_api_key(self) -> None:
        with patch.dict("os.environ", {"OPENTOPOGRAPHY_API_KEY": "   "}, clear=True):
            with pytest.raises(
                TopographyConfigError,
                match="OPENTOPOGRAPHY_API_KEY",
            ):
                TopographyConfig.from_env()

    def test_from_env_reads_min_bbox_side(self) -> None:
        with patch.dict(
            "os.environ",
            {
                "OPENTOPOGRAPHY_API_KEY": "test-key",
                "SSRI_OPENTOPO_MIN_BBOX_SIDE_M": "750",
            },
            clear=True,
        ):
            cfg = TopographyConfig.from_env()
        assert cfg.api_key == "test-key"
        assert cfg.min_bbox_side_m == 750.0


class TestBoundsResolution:
    def test_resolve_bounds_from_tuple(self) -> None:
        bounds = _resolve_bounds((-1.0, 50.0, 1.0, 52.0))
        assert bounds == (-1.0, 50.0, 1.0, 52.0)

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

        with patch.dict(sys.modules, {"ee": mock_ee}):
            bounds = _resolve_bounds(geometry)

        assert bounds == (-1.0, 50.0, 1.0, 52.0)

    def test_small_lagos_bbox_padded_for_opentopo(self) -> None:
        # ~180 m box around lon 3.423, lat 6.556 (product-like small AOI)
        half = 0.0008
        aoi = (3.423 - half, 6.556 - half, 3.423 + half, 6.556 + half)
        width_m, height_m = _bbox_side_lengths_m(aoi)
        assert width_m < 250.0
        assert height_m < 250.0

        padded = ensure_min_bbox_side_m(aoi, min_side_m=DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M)
        west, south, east, north = padded
        assert west < east
        assert south < north
        # Axis order preserved: index 0/2 longitude, 1/3 latitude
        assert west < 3.423 < east
        assert south < 6.556 < north
        pad_w, pad_h = _bbox_side_lengths_m(padded)
        assert pad_w >= DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M - 1.0
        assert pad_h >= DEFAULT_OPENTOPO_MIN_BBOX_SIDE_M - 1.0

    def test_download_dem_pads_tiny_aoi_in_request_params(
        self,
        tmp_path: Path,
        topo_config: TopographyConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SSRI_DEM_PROVIDER", "opentopo")
        geotiff_bytes = _grid_to_geotiff_bytes(_build_synthetic_grid(width=8, height=8))
        output_path = tmp_path / "tiny.tif"
        half = 0.0008
        aoi = (3.423 - half, 6.556 - half, 3.423 + half, 6.556 + half)

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "image/tiff"}
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[geotiff_bytes])

        with patch(
            "ssri_model.data.topography.requests.get",
            return_value=mock_response,
        ) as mock_get:
            download_dem(
                aoi,
                output_path,
                dem_type=DEMType.COPERNICUS,
                config=topo_config,
            )

        params = mock_get.call_args.kwargs["params"]
        assert params["demtype"] == "COP30"
        assert params["west"] < params["east"]
        assert params["south"] < params["north"]
        assert params["west"] < 3.423 < params["east"]
        assert params["south"] < 6.556 < params["north"]
        width_m, height_m = _bbox_side_lengths_m(
            (params["west"], params["south"], params["east"], params["north"])
        )
        assert width_m >= topo_config.min_bbox_side_m - 1.0
        assert height_m >= topo_config.min_bbox_side_m - 1.0


class TestDownloadDem:
    def test_download_dem_saves_geotiff(
        self,
        tmp_path: Path,
        topo_config: TopographyConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SSRI_DEM_PROVIDER", "opentopo")
        grid = _build_synthetic_grid(width=10, height=10)
        geotiff_bytes = _grid_to_geotiff_bytes(grid)
        output_path = tmp_path / "downloads" / "dem.tif"

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "image/tiff"}
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[geotiff_bytes])

        with patch(
            "ssri_model.data.topography.requests.get",
            return_value=mock_response,
        ) as mock_get:
            result = download_dem(
                (-1.0, 50.0, 1.0, 52.0),
                output_path,
                dem_type=DEMType.SRTM,
                config=topo_config,
            )

        assert result == output_path
        assert output_path.exists()
        mock_get.assert_called_once()
        request_params = mock_get.call_args.kwargs["params"]
        assert request_params["demtype"] == "SRTMGL1"
        assert request_params["API_Key"] == topo_config.api_key

        loaded = load_dem(output_path)
        assert loaded.width == grid.width
        assert loaded.height == grid.height

    def test_download_dem_supports_copernicus(
        self,
        tmp_path: Path,
        topo_config: TopographyConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SSRI_DEM_PROVIDER", "opentopo")
        geotiff_bytes = _grid_to_geotiff_bytes(_build_synthetic_grid(width=8, height=8))
        output_path = tmp_path / "cop30.tif"

        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "image/tiff"}
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(return_value=[geotiff_bytes])

        with patch(
            "ssri_model.data.topography.requests.get",
            return_value=mock_response,
        ) as mock_get:
            download_dem(
                (-1.0, 50.0, 1.0, 52.0),
                output_path,
                dem_type=DEMType.COPERNICUS,
                config=topo_config,
            )

        request_params = mock_get.call_args.kwargs["params"]
        assert request_params["demtype"] == "COP30"

    def test_download_dem_raises_on_http_error(
        self,
        tmp_path: Path,
        topo_config: TopographyConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        import requests

        monkeypatch.setenv("SSRI_DEM_PROVIDER", "opentopo")
        mock_response = MagicMock()
        mock_response.raise_for_status.side_effect = requests.HTTPError("403 Forbidden")

        with patch(
            "ssri_model.data.topography.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(TopographyDownloadError, match="OpenTopography request failed"):
                download_dem(
                    (-1.0, 50.0, 1.0, 52.0),
                    tmp_path / "dem.tif",
                    config=topo_config,
                )

    def test_download_dem_rejects_error_payload(
        self,
        tmp_path: Path,
        topo_config: TopographyConfig,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        monkeypatch.setenv("SSRI_DEM_PROVIDER", "opentopo")
        mock_response = MagicMock()
        mock_response.headers = {"Content-Type": "application/json"}
        mock_response.raise_for_status = MagicMock()
        mock_response.iter_content = MagicMock(
            return_value=[b'{"error": "invalid API key"}']
        )

        with patch(
            "ssri_model.data.topography.requests.get",
            return_value=mock_response,
        ):
            with pytest.raises(
                TopographyDownloadError,
                match="error response instead of GeoTIFF",
            ):
                download_dem(
                    (-1.0, 50.0, 1.0, 52.0),
                    tmp_path / "dem.tif",
                    config=topo_config,
                )


class TestLoadDem:
    def test_load_dem_preserves_grid_metadata(
        self,
        synthetic_dem: tuple[RasterGrid, Path],
    ) -> None:
        reference, dem_path = synthetic_dem
        loaded = load_dem(dem_path)

        assert loaded.width == reference.width
        assert loaded.height == reference.height
        assert loaded.transform == reference.transform
        assert loaded.crs == reference.crs
        assert loaded.nodata == reference.nodata
        np.testing.assert_allclose(loaded.data, reference.data)


class TestRelativeReliefAndValleyDepth:
    def test_compute_relative_relief_preserves_grid(
        self,
        synthetic_dem: tuple[RasterGrid, Path],
    ) -> None:
        dem, _ = synthetic_dem
        result = compute_relative_relief(dem)

        assert result.shape == dem.shape
        assert result.transform == dem.transform
        assert result.crs == dem.crs

    def test_compute_valley_depth_preserves_grid(
        self,
        synthetic_dem: tuple[RasterGrid, Path],
    ) -> None:
        dem, _ = synthetic_dem
        result = compute_valley_depth(dem)

        assert result.shape == dem.shape
        assert result.transform == dem.transform
        assert result.crs == dem.crs

    def test_derivatives_do_not_propagate_nan_into_valid_cells(
        self,
    ) -> None:
        dem = _build_synthetic_grid(nodata_fraction=0.1)
        valid = dem.data != dem.nodata

        relative_relief = compute_relative_relief(dem)
        valley_depth = compute_valley_depth(dem)

        assert np.all(np.isfinite(relative_relief.data[valid]))
        assert np.all(np.isfinite(valley_depth.data[valid]))
        assert np.all(relative_relief.data[~valid] == dem.nodata)
        assert np.all(valley_depth.data[~valid] == dem.nodata)

    def test_relative_relief_is_non_negative_on_valid_cells(
        self,
        synthetic_dem: tuple[RasterGrid, Path],
    ) -> None:
        dem, _ = synthetic_dem
        result = compute_relative_relief(dem)
        valid = dem.data != dem.nodata

        assert np.all(result.data[valid] >= 0.0)


class TestGridValidation:
    def test_validate_grid_alignment_detects_shape_mismatch(self) -> None:
        reference = _build_synthetic_grid(width=10, height=10)
        mismatched = RasterGrid(
            data=np.zeros((8, 8), dtype=np.float64),
            transform=reference.transform,
            crs=reference.crs,
            nodata=reference.nodata,
        )

        with pytest.raises(TopographyProcessingError, match="shape"):
            _validate_grid_alignment(reference, mismatched)


class TestWhiteboxDerivatives:
    def _mock_whitebox_output(self, dem: RasterGrid, scale: float) -> RasterGrid:
        """Simulate a WhiteboxTools output raster aligned to the DEM."""
        output = dem.data * scale
        return RasterGrid(
            data=output,
            transform=dem.transform,
            crs=dem.crs,
            nodata=dem.nodata,
        )

    @pytest.mark.parametrize(
        ("compute_fn", "scale"),
        [
            (compute_slope, 0.1),
            (compute_plan_curvature, 0.01),
            (compute_profile_curvature, 0.01),
        ],
    )
    def test_whitebox_derivatives_preserve_grid(
        self,
        synthetic_dem: tuple[RasterGrid, Path],
        compute_fn: object,
        scale: float,
    ) -> None:
        dem, _ = synthetic_dem

        def fake_run_whitebox_tool(
            input_dem: RasterGrid,
            tool: str,
            output_name: str,
            **kwargs: object,
        ) -> RasterGrid:
            return self._mock_whitebox_output(input_dem, scale)

        with patch(
            "ssri_model.data.topography._run_whitebox_tool",
            side_effect=fake_run_whitebox_tool,
        ):
            result = compute_fn(dem)

        assert result.shape == dem.shape
        assert result.transform == dem.transform
        assert result.crs == dem.crs
        valid = dem.data != dem.nodata
        assert np.all(np.isfinite(result.data[valid]))

    def test_compute_twi_uses_sca_and_slope(
        self,
        synthetic_dem: tuple[RasterGrid, Path],
    ) -> None:
        dem, _ = synthetic_dem

        def wetness_index(sca: str, slope: str, output: str, callback=None) -> bool:
            Path(output).write_bytes(b"placeholder")
            return True

        with (
            patch("ssri_model.data.topography._get_whitebox") as mock_get,
            patch("ssri_model.data.topography._write_geotiff"),
            patch(
                "ssri_model.data.topography._read_geotiff",
                return_value=self._mock_whitebox_output(dem, 2.0),
            ),
            patch("ssri_model.data.topography._validate_grid_alignment"),
            patch(
                "ssri_model.data.topography._apply_reference_nodata",
                side_effect=lambda _dem, data: data,
            ),
        ):
            wbt = mock_get.return_value
            wbt.slope.return_value = True
            wbt.fd8_flow_accumulation.return_value = True
            wbt.wetness_index.side_effect = wetness_index
            result = compute_twi(dem)

        wbt.fd8_flow_accumulation.assert_called_once()
        assert wbt.wetness_index.call_count == 1
        assert result.shape == dem.shape
        assert result.transform == dem.transform
