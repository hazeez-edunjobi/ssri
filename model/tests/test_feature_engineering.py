"""Tests for the SSRI feature stack builder."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.data.feature_engineering import (
    CHANNEL_ORDER,
    FeatureAlignmentError,
    FeatureStack,
    build_feature_stack,
    build_grid_spec_from_aoi,
)
from ssri_model.data.geophysics import GridSpec
from ssri_model.data.topography import RasterGrid


def _make_layer(
    value: float,
    grid_spec: GridSpec,
    offset: float = 0.0,
) -> RasterGrid:
    """Create a synthetic aligned raster layer."""
    data = np.full(grid_spec.shape, value + offset, dtype=np.float64)
    return RasterGrid(
        data=data,
        transform=grid_spec.transform,
        crs=grid_spec.crs,
        nodata=grid_spec.nodata,
    )


def _make_layers(grid_spec: GridSpec) -> dict[str, RasterGrid]:
    """Create one aligned raster for every channel."""
    return {
        name: _make_layer(float(index + 1), grid_spec)
        for index, name in enumerate(CHANNEL_ORDER)
    }


@pytest.fixture
def grid_spec() -> GridSpec:
    """Provide a small reference grid."""
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    crs = rasterio.crs.CRS.from_epsg(32613)
    return GridSpec(
        crs=crs,
        transform=transform,
        width=8,
        height=6,
        nodata=-9999.0,
    )


@pytest.fixture
def aligned_layers(grid_spec: GridSpec) -> dict[str, RasterGrid]:
    """Provide aligned layers for all channels."""
    return _make_layers(grid_spec)


class TestGridSpec:
    def test_build_grid_spec_from_aoi(self) -> None:
        spec = build_grid_spec_from_aoi((-1.0, 50.0, 1.0, 52.0), resolution_m=30.0)

        assert spec.width > 0
        assert spec.height > 0
        assert spec.resolution == (30.0, 30.0)


class TestFeatureStackExports:
    def test_save_numpy_geotiff_and_manifest(
        self,
        grid_spec: GridSpec,
        tmp_path: Path,
    ) -> None:
        tensor = np.stack(
            [layer.data for layer in _make_layers(grid_spec).values()],
            axis=0,
        )
        manifest = {
            "package_version": "0.1.0",
            "created_at": "2026-01-01T00:00:00+00:00",
            "channels": [{"index": i, "name": n} for i, n in enumerate(CHANNEL_ORDER, 1)],
            "tensor_shape": list(tensor.shape),
        }
        stack = FeatureStack(
            feature_tensor=tensor,
            channel_names=CHANNEL_ORDER,
            grid_spec=grid_spec,
            metadata={"resolution_m": 30.0},
            manifest=manifest,
        )

        npy_path = stack.save_numpy(tmp_path / "feature_stack.npy")
        tif_path = stack.save_geotiff(tmp_path / "feature_stack.tif")
        manifest_path = stack.save_manifest(tmp_path / "manifest.json")

        loaded = np.load(npy_path)
        assert loaded.shape == tensor.shape

        with rasterio.open(tif_path) as dataset:
            assert dataset.count == len(CHANNEL_ORDER)
            assert dataset.width == grid_spec.width
            assert dataset.height == grid_spec.height
            assert dataset.crs == grid_spec.crs

        saved_manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        assert saved_manifest["tensor_shape"] == list(tensor.shape)


class TestAlignmentValidation:
    def test_stack_layers_rejects_misaligned_layer(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
    ) -> None:
        from ssri_model.data.feature_engineering import _stack_layers

        bad = _make_layer(99.0, grid_spec)
        bad_grid = RasterGrid(
            data=np.zeros((4, 4), dtype=np.float64),
            transform=bad.transform,
            crs=bad.crs,
            nodata=bad.nodata,
        )
        layers = dict(aligned_layers)
        layers["slope"] = bad_grid

        with pytest.raises(FeatureAlignmentError, match="slope"):
            _stack_layers(layers, grid_spec)


class TestBuildFeatureStack:
    def _patch_pipeline(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
    ) -> dict[str, patch]:
        mock_sentinel = MagicMock(name="sentinel_composite")
        mock_spectral = MagicMock(name="spectral_index")

        return {
            "grid": patch(
                "ssri_model.data.feature_engineering.build_grid_spec_from_aoi",
                return_value=grid_spec,
            ),
            "sentinel": patch(
                "ssri_model.data.feature_engineering.get_sentinel_composite",
                return_value=mock_sentinel,
            ),
            "ndvi": patch(
                "ssri_model.data.feature_engineering.compute_ndvi",
                return_value=mock_spectral,
            ),
            "ndwi": patch(
                "ssri_model.data.feature_engineering.compute_ndwi",
                return_value=mock_spectral,
            ),
            "clay": patch(
                "ssri_model.data.feature_engineering.compute_clay_mineral_ratio",
                return_value=mock_spectral,
            ),
            "iron": patch(
                "ssri_model.data.feature_engineering.compute_iron_oxide_index",
                return_value=mock_spectral,
            ),
            "download_dem": patch(
                "ssri_model.data.feature_engineering.download_dem",
                return_value=Path("mock_dem.tif"),
            ),
            "load_dem": patch(
                "ssri_model.data.feature_engineering.load_dem",
                return_value=aligned_layers["elevation"],
            ),
            "slope": patch(
                "ssri_model.data.feature_engineering.compute_slope",
                return_value=aligned_layers["slope"],
            ),
            "plan": patch(
                "ssri_model.data.feature_engineering.compute_plan_curvature",
                return_value=aligned_layers["plan_curvature"],
            ),
            "profile": patch(
                "ssri_model.data.feature_engineering.compute_profile_curvature",
                return_value=aligned_layers["profile_curvature"],
            ),
            "twi": patch(
                "ssri_model.data.feature_engineering.compute_twi",
                return_value=aligned_layers["twi"],
            ),
            "relief": patch(
                "ssri_model.data.feature_engineering.compute_relative_relief",
                return_value=aligned_layers["relative_relief"],
            ),
            "valley": patch(
                "ssri_model.data.feature_engineering.compute_valley_depth",
                return_value=aligned_layers["valley_depth"],
            ),
            "spectral_grid": patch(
                "ssri_model.data.feature_engineering._spectral_index_to_grid",
                side_effect=[
                    aligned_layers["ndvi"],
                    aligned_layers["ndwi"],
                    aligned_layers["clay_mineral_ratio"],
                    aligned_layers["iron_oxide_index"],
                ],
            ),
            "gravity": patch(
                "ssri_model.data.feature_engineering.load_gravity",
                return_value=aligned_layers["gravity"],
            ),
            "magnetics": patch(
                "ssri_model.data.feature_engineering.load_magnetics",
                return_value=aligned_layers["magnetics"],
            ),
        }

    def test_build_feature_stack_channel_count_and_shape(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
    ) -> None:
        patches = self._patch_pipeline(grid_spec, aligned_layers)
        with patches["grid"], patches["sentinel"], patches["ndvi"], patches["ndwi"], patches[
            "clay"
        ], patches["iron"], patches["download_dem"], patches["load_dem"], patches[
            "slope"
        ], patches["plan"], patches["profile"], patches["twi"], patches[
            "relief"
        ], patches["valley"], patches["spectral_grid"], patches["gravity"], patches[
            "magnetics"
        ]:
            stack = build_feature_stack(
                (-1.0, 50.0, 1.0, 52.0),
                "2024-01-01",
                "2024-02-01",
                resolution_m=30.0,
            )

        assert stack.feature_tensor.shape == (
            len(CHANNEL_ORDER),
            grid_spec.height,
            grid_spec.width,
        )
        assert stack.channel_names == CHANNEL_ORDER

    def test_build_feature_stack_manifest_and_metadata(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
    ) -> None:
        patches = self._patch_pipeline(grid_spec, aligned_layers)
        with patches["grid"], patches["sentinel"], patches["ndvi"], patches["ndwi"], patches[
            "clay"
        ], patches["iron"], patches["download_dem"], patches["load_dem"], patches[
            "slope"
        ], patches["plan"], patches["profile"], patches["twi"], patches[
            "relief"
        ], patches["valley"], patches["spectral_grid"], patches["gravity"], patches[
            "magnetics"
        ]:
            stack = build_feature_stack(
                (-1.0, 50.0, 1.0, 52.0),
                "2024-01-01",
                "2024-02-01",
            )

        assert stack.manifest["tensor_shape"] == list(stack.feature_tensor.shape)
        assert len(stack.manifest["channels"]) == len(CHANNEL_ORDER)
        assert stack.manifest["channels"][0]["name"] == "elevation"
        assert stack.manifest["channels"][-1]["name"] == "magnetics"
        assert stack.metadata["resolution_m"] == 30.0
        assert stack.metadata["sources"]["gravity_provider"] == "wgm2012_bouguer"
        assert stack.metadata["sources"]["magnetic_provider"] == "emag2v3_uc4km"
        assert "channel_descriptions" in stack.metadata

    def test_build_feature_stack_writes_outputs(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
        tmp_path: Path,
    ) -> None:
        patches = self._patch_pipeline(grid_spec, aligned_layers)
        with patches["grid"], patches["sentinel"], patches["ndvi"], patches["ndwi"], patches[
            "clay"
        ], patches["iron"], patches["download_dem"], patches["load_dem"], patches[
            "slope"
        ], patches["plan"], patches["profile"], patches["twi"], patches[
            "relief"
        ], patches["valley"], patches["spectral_grid"], patches["gravity"], patches[
            "magnetics"
        ]:
            stack = build_feature_stack(
                (-1.0, 50.0, 1.0, 52.0),
                "2024-01-01",
                "2024-02-01",
                output_dir=tmp_path,
            )

        assert (tmp_path / "feature_stack.npy").exists()
        assert (tmp_path / "feature_stack.tif").exists()
        assert (tmp_path / "manifest.json").exists()
        assert stack.feature_tensor.ndim == 3

    def test_build_feature_stack_preserves_channel_order(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
    ) -> None:
        patches = self._patch_pipeline(grid_spec, aligned_layers)
        with patches["grid"], patches["sentinel"], patches["ndvi"], patches["ndwi"], patches[
            "clay"
        ], patches["iron"], patches["download_dem"], patches["load_dem"], patches[
            "slope"
        ], patches["plan"], patches["profile"], patches["twi"], patches[
            "relief"
        ], patches["valley"], patches["spectral_grid"], patches["gravity"], patches[
            "magnetics"
        ]:
            stack = build_feature_stack(
                (-1.0, 50.0, 1.0, 52.0),
                "2024-01-01",
                "2024-02-01",
            )

        for index, name in enumerate(CHANNEL_ORDER):
            expected = aligned_layers[name].data
            np.testing.assert_allclose(stack.feature_tensor[index], expected)

    def test_build_feature_stack_raises_on_alignment_failure(
        self,
        grid_spec: GridSpec,
        aligned_layers: dict[str, RasterGrid],
    ) -> None:
        bad_gravity = RasterGrid(
            data=np.zeros((4, 4), dtype=np.float64),
            transform=grid_spec.transform,
            crs=grid_spec.crs,
            nodata=grid_spec.nodata,
        )
        patches = self._patch_pipeline(grid_spec, aligned_layers)
        patches["gravity"] = patch(
            "ssri_model.data.feature_engineering.load_gravity",
            return_value=bad_gravity,
        )

        with patches["grid"], patches["sentinel"], patches["ndvi"], patches["ndwi"], patches[
            "clay"
        ], patches["iron"], patches["download_dem"], patches["load_dem"], patches[
            "slope"
        ], patches["plan"], patches["profile"], patches["twi"], patches[
            "relief"
        ], patches["valley"], patches["spectral_grid"], patches["gravity"], patches[
            "magnetics"
        ]:
            with pytest.raises(FeatureAlignmentError, match="gravity"):
                build_feature_stack(
                    (-1.0, 50.0, 1.0, 52.0),
                    "2024-01-01",
                    "2024-02-01",
                )
