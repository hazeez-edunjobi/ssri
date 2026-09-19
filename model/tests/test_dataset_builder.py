"""Tests for the SSRI Stage 2.1 dataset generation pipeline."""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import numpy as np
import pytest
import rasterio
from rasterio.transform import Affine

from ssri_model.data.feature_engineering import CHANNEL_ORDER, FeatureStack
from ssri_model.data.geophysics import GridSpec
from ssri_model.data.topography import RasterGrid
from ssri_model.ml.constants import CHANNEL_COUNT, DEFAULT_RANDOM_SEED, DEFAULT_SPLIT
from ssri_model.ml.splits import SplitConfig, split_sample_ids
from ssri_model.dataset.builder import DatasetBuildConfig, DatasetBuilder
from ssri_model.dataset.catalog import ML_CONTRACT_VERSION, load_catalog_manifest
from ssri_model.dataset.exceptions import (
    ChannelCountError,
    CorruptFileError,
    MetadataIncompleteError,
    MissingValueError,
    TensorShapeError,
)
from ssri_model.dataset.labels import LabelNotFoundError
from ssri_model.dataset.exporter import export_sample
from ssri_model.dataset.labels import LocalRasterLabelProvider
from ssri_model.dataset.sample import build_sample_metadata
from ssri_model.dataset.tiling import TilingConfig, tile_aoi, tile_aois
from ssri_model.dataset.validator import validate_sample_directory
from ssri_model.dataset.tiling import TileSpec


AOI = (-0.05, 51.0, 0.05, 51.05)
LARGE_AOI = (-1.0, 50.0, 1.0, 52.0)
START_DATE = "2024-01-01"
END_DATE = "2024-02-01"


def _grid_spec() -> GridSpec:
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    crs = rasterio.crs.CRS.from_epsg(32613)
    return GridSpec(
        crs=crs,
        transform=transform,
        width=8,
        height=6,
        nodata=-9999.0,
    )


def _make_layers(grid_spec: GridSpec) -> dict[str, RasterGrid]:
    return {
        name: RasterGrid(
            data=np.full(grid_spec.shape, float(index + 1), dtype=np.float64),
            transform=grid_spec.transform,
            crs=grid_spec.crs,
            nodata=grid_spec.nodata,
        )
        for index, name in enumerate(CHANNEL_ORDER)
    }


def _make_feature_stack(grid_spec: GridSpec | None = None) -> FeatureStack:
    spec = grid_spec or _grid_spec()
    tensor = np.stack(
        [layer.data for layer in _make_layers(spec).values()],
        axis=0,
    )
    return FeatureStack(
        feature_tensor=tensor,
        channel_names=CHANNEL_ORDER,
        grid_spec=spec,
        metadata={
            "resolution_m": 30.0,
            "dem": "COP30",
            "sentinel": "S2_SR",
            "gravity_provider": "wgm2012_bouguer",
            "magnetic_provider": "emag2v3_uc4km",
        },
        manifest={
            "package_version": "0.1.0",
            "created_at": "2026-08-07T09:00:00+00:00",
            "sources": {"dem": "COP30"},
            "tensor_shape": list(tensor.shape),
        },
    )


def _mock_build_feature_stack(aoi, start_date, end_date, resolution_m=30.0, output_dir=None):
    del aoi, start_date, end_date, resolution_m, output_dir
    return _make_feature_stack()


def _write_label_raster(path: Path, grid_spec: GridSpec, value: float = 1.0) -> None:
    profile = {
        "driver": "GTiff",
        "height": grid_spec.height,
        "width": grid_spec.width,
        "count": 1,
        "dtype": "float32",
        "crs": grid_spec.crs,
        "transform": grid_spec.transform,
        "nodata": grid_spec.nodata,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(np.full(grid_spec.shape, value, dtype=np.float32), 1)


class TestTiling:
    def test_tile_aoi_is_deterministic(self) -> None:
        config = TilingConfig(tile_size_m=120.0, overlap_m=30.0, id_prefix="tile")
        first = tile_aoi(AOI, config, resolution_m=30.0, aoi_index=0)
        second = tile_aoi(AOI, config, resolution_m=30.0, aoi_index=0)

        assert first == second
        assert len(first) > 1
        assert all(tile.tile_id.startswith("tile-a000-") for tile in first)

    def test_tile_aois_indexes_multiple_aois(self) -> None:
        config = TilingConfig(tile_size_m=300.0, overlap_m=0.0)
        tiles = tile_aois([AOI, (0.06, 51.0, 0.11, 51.05)], config, resolution_m=30.0)
        aoi_indexes = {tile.aoi_index for tile in tiles}
        assert aoi_indexes == {0, 1}

    def test_overlap_must_be_less_than_tile_size(self) -> None:
        with pytest.raises(ValueError, match="overlap_m must be less than tile_size_m"):
            TilingConfig(tile_size_m=100.0, overlap_m=100.0)


class TestSampleExport:
    def test_export_sample_writes_required_artifacts(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-a000-r0000-c0000", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
            created_at="2026-08-07T09:00:00+00:00",
        )
        label = np.ones(stack.grid_spec.shape, dtype=np.float32)

        sample = export_sample(
            tmp_path / tile.tile_id,
            stack=stack,
            metadata=metadata,
            label=label,
        )

        sample_dir = tmp_path / tile.tile_id
        assert (sample_dir / "feature_stack.npy").exists()
        assert (sample_dir / "label.tif").exists()
        assert (sample_dir / "metadata.json").exists()
        assert (sample_dir / "preview.png").exists()
        assert (sample_dir / "preview.png").stat().st_size > 0
        assert sample.sample_id == tile.tile_id

    def test_preview_image_generation(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-preview", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        export_sample(
            tmp_path / tile.tile_id,
            stack=stack,
            metadata=metadata,
            label=np.zeros(stack.grid_spec.shape, dtype=np.float32),
        )
        assert (tmp_path / tile.tile_id / "preview.png").exists()


class TestValidation:
    def test_validate_sample_directory_passes(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-valid", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        export_sample(tmp_path, stack=stack, metadata=metadata)
        loaded = validate_sample_directory(tmp_path)
        assert loaded.sample_id == tile.tile_id

    def test_validation_fails_for_bad_tensor_shape(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-bad", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        export_sample(tmp_path, stack=stack, metadata=metadata)
        np.save(tmp_path / "feature_stack.npy", np.zeros((5, 6, 8)))

        with pytest.raises(ChannelCountError):
            validate_sample_directory(tmp_path)

    def test_validation_fails_for_missing_file(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-missing", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        export_sample(tmp_path, stack=stack, metadata=metadata)
        (tmp_path / "preview.png").unlink()

        with pytest.raises(MissingValueError):
            validate_sample_directory(tmp_path)

    def test_validation_fails_for_incomplete_metadata(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-meta", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        export_sample(tmp_path, stack=stack, metadata=metadata)
        payload = json.loads((tmp_path / "metadata.json").read_text(encoding="utf-8"))
        del payload["crs"]
        (tmp_path / "metadata.json").write_text(json.dumps(payload), encoding="utf-8")

        with pytest.raises(MetadataIncompleteError):
            validate_sample_directory(tmp_path)

    def test_validation_fails_for_corrupt_numpy(self, tmp_path: Path) -> None:
        stack = _make_feature_stack()
        tile = TileSpec(tile_id="tile-corrupt", aoi=AOI, row=0, col=0)
        metadata = build_sample_metadata(
            sample_id=tile.tile_id,
            tile=tile,
            stack=stack,
            start_date=START_DATE,
            end_date=END_DATE,
        )
        export_sample(tmp_path, stack=stack, metadata=metadata)
        (tmp_path / "feature_stack.npy").write_bytes(b"not-numpy")

        with pytest.raises(CorruptFileError):
            validate_sample_directory(tmp_path)

    def test_tensor_shape_validation(self) -> None:
        with pytest.raises(TensorShapeError):
            from ssri_model.dataset.validator import validate_feature_tensor

            validate_feature_tensor(np.zeros((13, 4)), sample_id="bad")


class TestLocalRasterLabelProvider:
    def test_load_label_reprojects_to_target_grid(self, tmp_path: Path) -> None:
        grid_spec = _grid_spec()
        label_path = tmp_path / "tile-a000-r0000-c0000.tif"
        _write_label_raster(label_path, grid_spec, value=2.0)

        provider = LocalRasterLabelProvider(tmp_path)
        label = provider.load_label("tile-a000-r0000-c0000", grid_spec)

        assert label.shape == grid_spec.shape
        assert np.all(label == pytest.approx(2.0))

    def test_missing_label_raises(self, tmp_path: Path) -> None:
        provider = LocalRasterLabelProvider(tmp_path)
        with pytest.raises(LabelNotFoundError):
            provider.load_label("missing-tile", _grid_spec())


class TestDatasetBuilder:
    def test_dataset_generation_with_mocked_stage1(self, tmp_path: Path) -> None:
        config = DatasetBuildConfig(
            dataset_name="ssri-demo",
            version="0.1.0",
            output_dir=tmp_path,
            resolution_m=30.0,
            created_at="2026-08-07T09:00:00+00:00",
        )
        builder = DatasetBuilder(
            config,
            feature_stack_builder=_mock_build_feature_stack,
        )

        result = builder.build([AOI], START_DATE, END_DATE)

        assert result.dataset_root.exists()
        assert result.manifest_path.exists()
        assert result.statistics_path.exists()
        assert (result.dataset_root / "train").exists()
        assert (result.dataset_root / "validation").exists()
        assert (result.dataset_root / "test").exists()

        manifest = load_catalog_manifest(result.manifest_path)
        assert manifest["dataset_name"] == "ssri-demo"
        assert manifest["ml_contract_version"] == ML_CONTRACT_VERSION
        assert manifest["train_count"] + manifest["validation_count"] + manifest["test_count"] == len(
            result.samples
        )

        sample_dirs = list((result.dataset_root / "train").glob("*"))
        sample_dirs += list((result.dataset_root / "validation").glob("*"))
        sample_dirs += list((result.dataset_root / "test").glob("*"))
        assert sample_dirs
        for sample_dir in sample_dirs:
            validate_sample_directory(sample_dir)
            tensor = np.load(sample_dir / "feature_stack.npy")
            assert tensor.shape[0] == CHANNEL_COUNT

    def test_dataset_generation_with_tiling_and_labels(self, tmp_path: Path) -> None:
        label_dir = tmp_path / "labels"
        label_dir.mkdir()
        grid_spec = _grid_spec()

        config = DatasetBuildConfig(
            dataset_name="ssri-tiled",
            version="0.1.0",
            output_dir=tmp_path / "datasets",
            resolution_m=30.0,
            tiling=TilingConfig(tile_size_m=3000.0, overlap_m=0.0),
            label_provider=LocalRasterLabelProvider(label_dir),
            split_config=SplitConfig(
                train=DEFAULT_SPLIT["train"],
                validation=DEFAULT_SPLIT["validation"],
                test=DEFAULT_SPLIT["test"],
                random_seed=DEFAULT_RANDOM_SEED,
            ),
            created_at="2026-08-07T09:00:00+00:00",
        )

        tiles = tile_aoi(AOI, config.tiling, resolution_m=30.0)
        for tile in tiles:
            _write_label_raster(label_dir / f"{tile.tile_id}.tif", grid_spec)

        builder = DatasetBuilder(
            config,
            feature_stack_builder=_mock_build_feature_stack,
        )
        result = builder.build([AOI], START_DATE, END_DATE)

        stats = json.loads(result.statistics_path.read_text(encoding="utf-8"))
        assert stats["sample_count"] == len(tiles)
        assert stats["label_present_count"] == len(tiles)

    def test_manifest_generation_records_split_counts(self, tmp_path: Path) -> None:
        sample_ids = [f"sample-{index:03d}" for index in range(10)]
        split = split_sample_ids(
            sample_ids,
            SplitConfig(
                train=0.7,
                validation=0.15,
                test=0.15,
                random_seed=DEFAULT_RANDOM_SEED,
            ),
        )

        config = DatasetBuildConfig(
            dataset_name="ssri-split",
            version="0.1.0",
            output_dir=tmp_path,
            created_at="2026-08-07T09:00:00+00:00",
        )
        builder = DatasetBuilder(
            config,
            feature_stack_builder=_mock_build_feature_stack,
        )

        with patch.object(builder, "_resolve_tiles") as mock_tiles:
            mock_tiles.return_value = [
                TileSpec(tile_id=sample_id, aoi=AOI, row=0, col=index)
                for index, sample_id in enumerate(sample_ids)
            ]
            result = builder.build([AOI], START_DATE, END_DATE)

        manifest = load_catalog_manifest(result.manifest_path)
        assert manifest["train_count"] == len(split.train)
        assert manifest["validation_count"] == len(split.validation)
        assert manifest["test_count"] == len(split.test)
        assert set(manifest["splits"]["train"]) == set(split.train)

    def test_deterministic_splits_in_dataset_build(self, tmp_path: Path) -> None:
        config = DatasetBuildConfig(
            dataset_name="ssri-deterministic",
            version="0.1.0",
            output_dir=tmp_path,
            split_config=SplitConfig(random_seed=DEFAULT_RANDOM_SEED),
            created_at="2026-08-07T09:00:00+00:00",
        )
        sample_ids = [f"sample-{index:03d}" for index in range(20)]

        def build_once() -> tuple[tuple[str, ...], tuple[str, ...], tuple[str, ...]]:
            builder = DatasetBuilder(
                config,
                feature_stack_builder=_mock_build_feature_stack,
            )
            with patch.object(builder, "_resolve_tiles") as mock_tiles:
                mock_tiles.return_value = [
                    TileSpec(tile_id=sample_id, aoi=AOI, row=0, col=index)
                    for index, sample_id in enumerate(sample_ids)
                ]
                result = builder.build([AOI], START_DATE, END_DATE)
            return result.split.train, result.split.validation, result.split.test

        assert build_once() == build_once()
