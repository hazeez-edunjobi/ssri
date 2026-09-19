"""Stage 1 end-to-end integration tests for the SSRI feature pipeline."""

from __future__ import annotations

import json
import time
import tracemalloc
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.data.feature_engineering import (
    CHANNEL_ORDER,
    FeatureAlignmentError,
    build_feature_stack,
)
from ssri_model.data.gee_client import (
    GEEAuthenticationError,
    initialize,
    reset_initialization,
)
from ssri_model.data.geophysics import (
    GeophysicsAlignmentError,
    GeophysicsConfigError,
    GeophysicsDataError,
    GridSpec,
    validate_alignment,
)
from ssri_model.data.spectral import MissingBandError, compute_ndvi
from ssri_model.data.topography import (
    TopographyConfigError,
    TopographyDownloadError,
    RasterGrid,
)

AOI = (-1.0, 50.0, 1.0, 52.0)
START_DATE = "2024-01-01"
END_DATE = "2024-02-01"
RESOLUTION_M = 30.0


def _grid_spec() -> GridSpec:
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    crs = rasterio.crs.CRS.from_epsg(32613)
    return GridSpec(crs=crs, transform=transform, width=8, height=6, nodata=-9999.0)


def _layer(value: float, spec: GridSpec) -> RasterGrid:
    return RasterGrid(
        data=np.full(spec.shape, value, dtype=np.float64),
        transform=spec.transform,
        crs=spec.crs,
        nodata=spec.nodata,
    )


def _all_layers(spec: GridSpec) -> dict[str, RasterGrid]:
    return {name: _layer(float(i + 1), spec) for i, name in enumerate(CHANNEL_ORDER)}


@contextmanager
def _pipeline_mocks(
    spec: GridSpec,
    layers: dict[str, RasterGrid],
) -> Iterator[dict[str, MagicMock | patch]]:
    mock_sentinel = MagicMock(name="sentinel")
    mock_index = MagicMock(name="spectral_index")
    patches = {
        "grid_spec": patch(
            "ssri_model.data.feature_engineering.build_grid_spec_from_aoi",
            return_value=spec,
        ),
        "initialize": patch("ssri_model.data.gee_client.initialize"),
        "sentinel": patch(
            "ssri_model.data.feature_engineering.get_sentinel_composite",
            return_value=mock_sentinel,
        ),
        "ndvi": patch(
            "ssri_model.data.feature_engineering.compute_ndvi",
            return_value=mock_index,
        ),
        "ndwi": patch(
            "ssri_model.data.feature_engineering.compute_ndwi",
            return_value=mock_index,
        ),
        "clay": patch(
            "ssri_model.data.feature_engineering.compute_clay_mineral_ratio",
            return_value=mock_index,
        ),
        "iron": patch(
            "ssri_model.data.feature_engineering.compute_iron_oxide_index",
            return_value=mock_index,
        ),
        "download_dem": patch(
            "ssri_model.data.feature_engineering.download_dem",
            return_value=Path("dem.tif"),
        ),
        "load_dem": patch(
            "ssri_model.data.feature_engineering.load_dem",
            return_value=layers["elevation"],
        ),
        "slope": patch(
            "ssri_model.data.feature_engineering.compute_slope",
            return_value=layers["slope"],
        ),
        "plan": patch(
            "ssri_model.data.feature_engineering.compute_plan_curvature",
            return_value=layers["plan_curvature"],
        ),
        "profile": patch(
            "ssri_model.data.feature_engineering.compute_profile_curvature",
            return_value=layers["profile_curvature"],
        ),
        "twi": patch(
            "ssri_model.data.feature_engineering.compute_twi",
            return_value=layers["twi"],
        ),
        "relief": patch(
            "ssri_model.data.feature_engineering.compute_relative_relief",
            return_value=layers["relative_relief"],
        ),
        "valley": patch(
            "ssri_model.data.feature_engineering.compute_valley_depth",
            return_value=layers["valley_depth"],
        ),
        "spectral_grid": patch(
            "ssri_model.data.feature_engineering._spectral_index_to_grid",
            side_effect=[
                layers["ndvi"],
                layers["ndwi"],
                layers["clay_mineral_ratio"],
                layers["iron_oxide_index"],
            ],
        ),
        "gravity": patch(
            "ssri_model.data.feature_engineering.load_gravity",
            return_value=layers["gravity"],
        ),
        "magnetics": patch(
            "ssri_model.data.feature_engineering.load_magnetics",
            return_value=layers["magnetics"],
        ),
    }

    started = {key: patcher.start() for key, patcher in patches.items()}
    try:
        yield started
    finally:
        for patcher in patches.values():
            patcher.stop()


@pytest.fixture(autouse=True)
def reset_gee() -> Iterator[None]:
    reset_initialization()
    yield
    reset_initialization()


class TestStage1EndToEndPipeline:
    def test_full_pipeline_integration(self, tmp_path: Path) -> None:
        spec = _grid_spec()
        layers = _all_layers(spec)
        timings: dict[str, float] = {}
        tracemalloc.start()

        total_start = time.perf_counter()
        with _pipeline_mocks(spec, layers) as mocks:
            stage_start = time.perf_counter()
            stack = build_feature_stack(
                AOI,
                START_DATE,
                END_DATE,
                resolution_m=RESOLUTION_M,
                output_dir=tmp_path,
            )
            timings["build_feature_stack"] = time.perf_counter() - stage_start

        total_elapsed = time.perf_counter() - total_start
        _, peak_memory = tracemalloc.get_traced_memory()
        tracemalloc.stop()

        # Step 1–2: GEE + spectral invoked
        mocks["initialize"]  # EE init happens inside get_sentinel_composite in prod
        mocks["sentinel"].assert_called_once()
        mocks["ndvi"].assert_called_once()
        mocks["ndwi"].assert_called_once()
        mocks["clay"].assert_called_once()
        mocks["iron"].assert_called_once()

        # Step 3–4: DEM + terrain
        mocks["download_dem"].assert_called_once()
        mocks["load_dem"].assert_called_once()
        mocks["slope"].assert_called_once()
        mocks["plan"].assert_called_once()
        mocks["profile"].assert_called_once()
        mocks["twi"].assert_called_once()
        mocks["relief"].assert_called_once()
        mocks["valley"].assert_called_once()

        # Step 5–6: Geophysics
        mocks["gravity"].assert_called_once()
        mocks["magnetics"].assert_called_once()

        # Tensor shape
        assert stack.feature_tensor.shape == (
            13,
            spec.height,
            spec.width,
        )

        # Channel order vs manifest
        manifest_channels = [entry["name"] for entry in stack.manifest["channels"]]
        assert manifest_channels == list(CHANNEL_ORDER)
        assert stack.channel_names == CHANNEL_ORDER
        assert len(set(manifest_channels)) == 13

        # Metadata consistency
        assert stack.metadata["resolution_m"] == RESOLUTION_M
        assert stack.metadata["crs"] == stack.manifest["crs"]
        assert stack.metadata["acquisition"]["start_date"] == START_DATE
        assert stack.manifest["tensor_shape"] == list(stack.feature_tensor.shape)

        # Alignment: every channel matches reference grid
        for index, name in enumerate(CHANNEL_ORDER):
            layer = RasterGrid(
                data=stack.feature_tensor[index],
                transform=stack.grid_spec.transform,
                crs=stack.grid_spec.crs,
                nodata=stack.grid_spec.nodata,
            )
            validate_alignment(stack.grid_spec, layer)

        # Exports
        assert (tmp_path / "feature_stack.npy").exists()
        assert (tmp_path / "feature_stack.tif").exists()
        assert (tmp_path / "manifest.json").exists()

        loaded = np.load(tmp_path / "feature_stack.npy")
        assert loaded.shape == stack.feature_tensor.shape

        with rasterio.open(tmp_path / "feature_stack.tif") as dataset:
            assert dataset.count == 13
            assert dataset.width == spec.width
            assert dataset.height == spec.height
            assert dataset.crs == spec.crs
            assert dataset.transform == spec.transform

        saved_manifest = json.loads(
            (tmp_path / "manifest.json").read_text(encoding="utf-8")
        )
        assert saved_manifest["channels"][0]["name"] == "elevation"
        assert saved_manifest["channels"][-1]["name"] == "magnetics"

        # Deterministic given mocked inputs
        for index, name in enumerate(CHANNEL_ORDER):
            np.testing.assert_allclose(
                stack.feature_tensor[index],
                layers[name].data,
            )

        # Performance metrics stored for QA report
        pytest.pipeline_total_seconds = total_elapsed  # type: ignore[attr-defined]
        pytest.pipeline_peak_memory_mb = peak_memory / (1024 * 1024)  # type: ignore[attr-defined]
        pytest.pipeline_stage_timings = timings  # type: ignore[attr-defined]

    def test_deterministic_output_across_runs(self, tmp_path: Path) -> None:
        spec = _grid_spec()
        layers = _all_layers(spec)

        with _pipeline_mocks(spec, layers):
            first = build_feature_stack(AOI, START_DATE, END_DATE, resolution_m=RESOLUTION_M)
        with _pipeline_mocks(spec, layers):
            second = build_feature_stack(AOI, START_DATE, END_DATE, resolution_m=RESOLUTION_M)

        np.testing.assert_array_equal(first.feature_tensor, second.feature_tensor)


class TestStage1FailureInjection:
    def test_missing_sentinel_band_raises(self) -> None:
        composite = {"B2": np.ones((4, 4))}
        with pytest.raises(MissingBandError, match="Missing required Sentinel-2 bands"):
            compute_ndvi(composite)

    def test_dem_unavailable_raises(self) -> None:
        spec = _grid_spec()
        layers = _all_layers(spec)
        with _pipeline_mocks(spec, layers):
            with patch(
                "ssri_model.data.feature_engineering.download_dem",
                side_effect=TopographyDownloadError("OpenTopography request failed"),
            ):
                with pytest.raises(TopographyDownloadError, match="OpenTopography"):
                    build_feature_stack(AOI, START_DATE, END_DATE)

    def test_gravity_unavailable_raises(self) -> None:
        spec = _grid_spec()
        layers = _all_layers(spec)
        with _pipeline_mocks(spec, layers):
            with patch(
                "ssri_model.data.feature_engineering.load_gravity",
                side_effect=GeophysicsDataError("Geophysical dataset not found"),
            ):
                with pytest.raises(GeophysicsDataError, match="unavailable|not found"):
                    build_feature_stack(AOI, START_DATE, END_DATE)

    def test_magnetic_unavailable_raises(self) -> None:
        spec = _grid_spec()
        layers = _all_layers(spec)
        with _pipeline_mocks(spec, layers):
            with patch(
                "ssri_model.data.feature_engineering.load_magnetics",
                side_effect=GeophysicsConfigError("MAGNETIC_DATA_PATH"),
            ):
                with pytest.raises(GeophysicsConfigError, match="MAGNETIC_DATA_PATH"):
                    build_feature_stack(AOI, START_DATE, END_DATE)

    def test_crs_mismatch_raises(self) -> None:
        spec = _grid_spec()
        bad = _layer(99.0, spec)
        bad_crs = RasterGrid(
            data=bad.data,
            transform=bad.transform,
            crs=rasterio.crs.CRS.from_epsg(32614),
            nodata=bad.nodata,
        )
        with pytest.raises(GeophysicsAlignmentError, match="CRS mismatch"):
            validate_alignment(spec, bad_crs)

    def test_transform_mismatch_raises(self) -> None:
        spec = _grid_spec()
        shifted = Affine(30.0, 0.0, 500030.0, 0.0, -30.0, 4100000.0)
        layer = RasterGrid(
            data=np.ones(spec.shape),
            transform=shifted,
            crs=spec.crs,
            nodata=spec.nodata,
        )
        with pytest.raises(GeophysicsAlignmentError, match="Affine transform mismatch"):
            validate_alignment(spec, layer)

    def test_width_mismatch_raises(self) -> None:
        spec = _grid_spec()
        layer = RasterGrid(
            data=np.ones((spec.height, spec.width + 2)),
            transform=spec.transform,
            crs=spec.crs,
            nodata=spec.nodata,
        )
        with pytest.raises(GeophysicsAlignmentError, match="Shape mismatch"):
            validate_alignment(spec, layer)

    def test_gravity_misalignment_in_pipeline_raises(self) -> None:
        spec = _grid_spec()
        layers = _all_layers(spec)
        bad_gravity = RasterGrid(
            data=np.zeros((4, 4), dtype=np.float64),
            transform=spec.transform,
            crs=spec.crs,
            nodata=spec.nodata,
        )
        with _pipeline_mocks(spec, layers):
            with patch(
                "ssri_model.data.feature_engineering.load_gravity",
                return_value=bad_gravity,
            ):
                with pytest.raises(FeatureAlignmentError, match="gravity"):
                    build_feature_stack(AOI, START_DATE, END_DATE)

    def test_missing_gee_env_raises(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(GEEAuthenticationError, match="Missing required"):
                initialize()

    def test_missing_topography_env_raises(self) -> None:
        from ssri_model.data.topography import TopographyConfig

        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(TopographyConfigError, match="OPENTOPOGRAPHY_API_KEY"):
                TopographyConfig.from_env()

    def test_missing_geophysics_env_raises(self) -> None:
        from ssri_model.data.geophysics import EIGEN6C4Provider, GeophysicsConfig

        config = GeophysicsConfig(gravity_data_path=None, magnetic_data_path=None)
        provider = EIGEN6C4Provider(config=config)

        with pytest.raises(GeophysicsConfigError, match="GRAVITY_DATA_PATH"):
            provider.load_gravity(AOI)


class TestStage1ModuleUnitCoverage:
    """Run all Stage 1 unit tests as part of integration gate."""

    def test_all_stage1_unit_tests_pass(self) -> None:
        exit_code = pytest.main(
            [
                "tests/test_gee_client.py",
                "tests/test_topography.py",
                "tests/test_spectral.py",
                "tests/test_geophysics.py",
                "tests/test_feature_engineering.py",
                "-q",
            ]
        )
        assert exit_code == 0
