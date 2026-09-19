"""Tests for Stage 2.2 PyTorch dataset, normalization, and dataloader."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
import torch
from rasterio.transform import Affine

from ssri_model.data.feature_engineering import CHANNEL_ORDER
from ssri_model.data.geophysics import GridSpec
from ssri_model.ml.constants import (
    CHANNEL_COUNT,
    FEATURE_NODATA,
    LABEL_NODATA,
)
from ssri_model.ml.dataloader import create_dataloader
from ssri_model.ml.dataset import SSRIDataset
from ssri_model.ml.dataset_spec import DatasetManifest
from ssri_model.ml.exceptions import (
    BatchShapeError,
    EmptyDatasetError,
    InvalidFeatureTensorError,
    InvalidLabelError,
    StatisticsError,
    SplitError,
)
from ssri_model.ml.normalization import (
    NormalizationConfig,
    NormalizationMethod,
    normalize_channel_array,
    normalize_feature_stack,
)
from ssri_model.ml.statistics_loader import (
    ChannelStatistics,
    FeatureStatistics,
    compute_feature_statistics_from_arrays,
    load_feature_statistics,
)
from ssri_model.ml.transforms import HorizontalFlip, Rotate90, VerticalFlip
from ssri_model.dataset.catalog import write_manifest
from ssri_model.ml.splits import DatasetSplit


def _grid_spec(width: int = 8, height: int = 8) -> GridSpec:
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    return GridSpec(
        crs=rasterio.crs.CRS.from_epsg(32613),
        transform=transform,
        width=width,
        height=height,
        nodata=FEATURE_NODATA,
    )


def _write_label(path: Path, grid_spec: GridSpec, value: float = 0.0) -> None:
    profile = {
        "driver": "GTiff",
        "height": grid_spec.height,
        "width": grid_spec.width,
        "count": 1,
        "dtype": "float32",
        "crs": grid_spec.crs,
        "transform": grid_spec.transform,
        "nodata": FEATURE_NODATA,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        data = np.full(grid_spec.shape, value, dtype=np.float32)
        dataset.write(data, 1)


def _write_sample(
    sample_dir: Path,
    *,
    width: int = 8,
    height: int = 8,
    channel_offset: float = 0.0,
    label_value: float = 0.0,
    nodata_pixels: bool = False,
) -> np.ndarray:
    sample_dir.mkdir(parents=True, exist_ok=True)
    grid_spec = _grid_spec(width=width, height=height)
    tensor = np.stack(
        [
            np.full((height, width), float(index + 1) + channel_offset, dtype=np.float64)
            for index in range(CHANNEL_COUNT)
        ],
        axis=0,
    )
    if nodata_pixels:
        tensor[:, 0, 0] = FEATURE_NODATA

    np.save(sample_dir / "feature_stack.npy", tensor)
    _write_label(sample_dir / "label.tif", grid_spec, value=label_value)
    metadata = {
        "sample_id": sample_dir.name,
        "aoi": {"bbox_wgs84": {"min_lon": -1, "min_lat": 50, "max_lon": 1, "max_lat": 52}},
        "acquisition": {"start_date": "2024-01-01", "end_date": "2024-02-01"},
        "resolution_m": 30.0,
        "crs": str(grid_spec.crs),
        "sources": {"dem": "COP30"},
        "package_version": "0.1.0",
        "created_at": "2026-08-07T09:00:00+00:00",
    }
    (sample_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tensor


def _write_synthetic_dataset(
    root: Path,
    *,
    sample_ids: list[str],
    width: int = 8,
    height: int = 8,
) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    tensors = []
    for index, sample_id in enumerate(sample_ids):
        split_name = "train" if index == 0 else "validation"
        sample_dir = root / split_name / sample_id
        tensors.append(
            _write_sample(
                sample_dir,
                width=width,
                height=height,
                channel_offset=float(index),
                label_value=float(index % 3),
            )
        )

    split = DatasetSplit(
        train=(sample_ids[0],),
        validation=(sample_ids[1],) if len(sample_ids) > 1 else (),
        test=(),
    )
    write_manifest(
        root,
        dataset_name="synthetic",
        version="0.1.0",
        split=split,
        crs="EPSG:32613",
    )

    stats = compute_feature_statistics_from_arrays(tensors)
    statistics_payload = {
        "sample_count": len(sample_ids),
        "train_count": len(split.train),
        "validation_count": len(split.validation),
        "test_count": len(split.test),
        "channel_names": list(CHANNEL_ORDER),
        "channel_stats": {
            name: {
                "min": stat.min,
                "max": stat.max,
                "mean": stat.mean,
                "std": stat.std,
                "valid_count": stat.valid_count,
                "nodata_count": stat.nodata_count,
            }
            for name, stat in stats.channels.items()
        },
        "label_present_count": len(sample_ids),
        "created_at": "2026-08-07T09:00:00+00:00",
    }
    (root / "statistics.json").write_text(json.dumps(statistics_payload), encoding="utf-8")
    return root


@pytest.fixture
def synthetic_dataset(tmp_path: Path) -> Path:
    return _write_synthetic_dataset(
        tmp_path / "dataset",
        sample_ids=["sample-a", "sample-b"],
    )


class TestStatisticsLoader:
    def test_load_feature_statistics(self, synthetic_dataset: Path) -> None:
        stats = load_feature_statistics(synthetic_dataset / "statistics.json")
        assert stats.channel_count == CHANNEL_COUNT
        assert "elevation" in stats.channels

    def test_missing_statistics_file(self, tmp_path: Path) -> None:
        with pytest.raises(StatisticsError):
            load_feature_statistics(tmp_path / "missing.json")

    def test_missing_valid_count_rejected(self, tmp_path: Path) -> None:
        payload = {
            "channel_stats": {
                name: {"min": 1.0, "max": 2.0, "mean": 1.5, "std": 0.5}
                for name in CHANNEL_ORDER
            }
        }
        path = tmp_path / "statistics.json"
        path.write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(StatisticsError):
            load_feature_statistics(path)

    def test_invalid_statistics_nan(self) -> None:
        with pytest.raises(StatisticsError):
            ChannelStatistics(
                min=float("nan"),
                max=1.0,
                mean=1.0,
                std=1.0,
                valid_count=1,
                nodata_count=0,
            )


class TestNormalization:
    def test_z_score_normalization(self) -> None:
        values = np.array([[10.0, FEATURE_NODATA], [12.0, 14.0]], dtype=np.float64)
        mask = values != FEATURE_NODATA
        stats = ChannelStatistics(
            min=10.0, max=14.0, mean=12.0, std=2.0, valid_count=3, nodata_count=1
        )
        normalized = normalize_channel_array(
            values,
            valid_mask=mask,
            stats=stats,
            method=NormalizationMethod.Z_SCORE,
        )
        assert normalized[0, 0] == pytest.approx(-1.0)
        assert normalized[0, 1] == 0.0
        assert np.isfinite(normalized[mask]).all()

    def test_min_max_normalization(self) -> None:
        values = np.array([[0.0, 5.0], [10.0, FEATURE_NODATA]], dtype=np.float64)
        mask = values != FEATURE_NODATA
        stats = ChannelStatistics(
            min=0.0, max=10.0, mean=5.0, std=3.0, valid_count=3, nodata_count=1
        )
        normalized = normalize_channel_array(
            values,
            valid_mask=mask,
            stats=stats,
            method=NormalizationMethod.MIN_MAX,
        )
        assert normalized[0, 0] == pytest.approx(0.0)
        assert normalized[0, 1] == pytest.approx(0.5)
        assert normalized[1, 0] == pytest.approx(1.0)

    def test_identity_normalization(self) -> None:
        values = np.array([[3.0, FEATURE_NODATA]], dtype=np.float64)
        mask = values != FEATURE_NODATA
        stats = ChannelStatistics(
            min=3.0, max=3.0, mean=3.0, std=0.0, valid_count=1, nodata_count=1
        )
        normalized = normalize_channel_array(
            values,
            valid_mask=mask,
            stats=stats,
            method=NormalizationMethod.IDENTITY,
        )
        assert normalized[0, 0] == pytest.approx(3.0)
        assert normalized[0, 1] == 0.0

    def test_zero_std_is_safe(self) -> None:
        values = np.array([[4.0, 4.0]], dtype=np.float64)
        mask = np.ones_like(values, dtype=bool)
        stats = ChannelStatistics(
            min=4.0, max=4.0, mean=4.0, std=0.0, valid_count=2, nodata_count=0
        )
        normalized = normalize_channel_array(
            values,
            valid_mask=mask,
            stats=stats,
            method=NormalizationMethod.Z_SCORE,
        )
        assert np.isfinite(normalized).all()

    def test_equal_min_max_is_safe(self) -> None:
        values = np.array([[2.0, 2.0]], dtype=np.float64)
        mask = np.ones_like(values, dtype=bool)
        stats = ChannelStatistics(
            min=2.0, max=2.0, mean=2.0, std=0.0, valid_count=2, nodata_count=0
        )
        normalized = normalize_channel_array(
            values,
            valid_mask=mask,
            stats=stats,
            method=NormalizationMethod.MIN_MAX,
        )
        assert np.isfinite(normalized).all()

    def test_nodata_not_normalized(self) -> None:
        tensor = np.full((CHANNEL_COUNT, 4, 4), FEATURE_NODATA, dtype=np.float64)
        tensor[:, 1:, 1:] = 5.0
        mask = np.all(tensor != FEATURE_NODATA, axis=0)
        channels = {
            name: ChannelStatistics(
                min=5.0, max=5.0, mean=5.0, std=1.0, valid_count=9, nodata_count=7
            )
            for name in CHANNEL_ORDER
        }
        stats = FeatureStatistics(channel_names=CHANNEL_ORDER, channels=channels)
        config = NormalizationConfig.default()
        normalized = normalize_feature_stack(
            tensor, valid_mask=mask, statistics=stats, config=config
        )
        assert (normalized[:, ~mask] == 0.0).all()


class TestSSRIDataset:
    def test_dataset_initialization(self, synthetic_dataset: Path) -> None:
        dataset = SSRIDataset(synthetic_dataset, split="train")
        assert len(dataset) == 1

    def test_feature_and_label_loading(self, synthetic_dataset: Path) -> None:
        dataset = SSRIDataset(synthetic_dataset, split="train")
        sample = dataset[0]
        assert sample["features"].shape == (CHANNEL_COUNT, 8, 8)
        assert sample["label"].shape == (8, 8)
        assert sample["mask"].shape == (8, 8)
        assert sample["features"].dtype == torch.float32
        assert sample["label"].dtype == torch.int64

    def test_wrong_channel_count_rejected(self, synthetic_dataset: Path) -> None:
        sample_dir = synthetic_dataset / "train" / "sample-a"
        np.save(sample_dir / "feature_stack.npy", np.zeros((5, 8, 8)))
        dataset = SSRIDataset(synthetic_dataset, split="train")
        with pytest.raises(InvalidFeatureTensorError):
            dataset[0]

    def test_invalid_label_rejected(self, synthetic_dataset: Path) -> None:
        sample_dir = synthetic_dataset / "train" / "sample-a"
        _write_label(sample_dir / "label.tif", _grid_spec(), value=99.0)
        dataset = SSRIDataset(synthetic_dataset, split="train")
        with pytest.raises(InvalidLabelError):
            dataset[0]

    def test_nodata_masking(self, synthetic_dataset: Path) -> None:
        sample_dir = synthetic_dataset / "train" / "sample-a"
        _write_sample(sample_dir, nodata_pixels=True)
        dataset = SSRIDataset(synthetic_dataset, split="train")
        sample = dataset[0]
        assert sample["mask"].dtype == torch.bool
        assert sample["mask"][0, 0].item() is False
        assert sample["features"][:, 0, 0].eq(0.0).all()

    def test_split_isolation(self, synthetic_dataset: Path) -> None:
        train = SSRIDataset(synthetic_dataset, split="train")
        val = SSRIDataset(synthetic_dataset, split="validation")
        assert train[0]["sample_id"] == "sample-a"
        assert val[0]["sample_id"] == "sample-b"

    def test_empty_dataset(self, synthetic_dataset: Path) -> None:
        dataset = SSRIDataset(synthetic_dataset, split="test")
        assert len(dataset) == 0
        with pytest.raises(EmptyDatasetError):
            dataset[0]


class TestTransforms:
    def _sample(self) -> dict[str, torch.Tensor]:
        features = torch.arange(CHANNEL_COUNT * 4 * 4, dtype=torch.float32).reshape(
            CHANNEL_COUNT, 4, 4
        )
        label = torch.arange(16, dtype=torch.int64).reshape(4, 4)
        mask = torch.ones(4, 4, dtype=torch.bool)
        return {
            "features": features,
            "label": label,
            "mask": mask,
            "sample_id": "sample-x",
        }

    def test_horizontal_flip_synchronization(self) -> None:
        transform = HorizontalFlip(probability=1.0)
        sample = transform(self._sample())
        assert torch.equal(sample["features"], torch.flip(self._sample()["features"], dims=(-1,)))
        assert torch.equal(sample["label"], torch.flip(self._sample()["label"], dims=(-1,)))
        assert torch.equal(sample["mask"], torch.flip(self._sample()["mask"], dims=(-1,)))

    def test_vertical_flip_synchronization(self) -> None:
        transform = VerticalFlip(probability=1.0)
        sample = transform(self._sample())
        assert torch.equal(sample["features"], torch.flip(self._sample()["features"], dims=(-2,)))
        assert torch.equal(sample["label"], torch.flip(self._sample()["label"], dims=(-2,)))
        assert torch.equal(sample["mask"], torch.flip(self._sample()["mask"], dims=(-2,)))

    def test_rotation_synchronization(self) -> None:
        transform = Rotate90(probability=1.0)
        sample = transform(self._sample())
        base = self._sample()
        assert torch.equal(
            sample["features"], torch.rot90(base["features"], k=-1, dims=(-2, -1))
        )
        assert torch.equal(sample["label"], torch.rot90(base["label"], k=-1, dims=(-2, -1)))
        assert torch.equal(sample["mask"], torch.rot90(base["mask"], k=-1, dims=(-2, -1)))

    def test_deterministic_augmentation_with_seed(self) -> None:
        transform = HorizontalFlip(probability=0.5)
        transform.set_seed(123)
        first = transform(self._sample())
        transform.set_seed(123)
        second = transform(self._sample())
        assert torch.equal(first["features"], second["features"])


class TestDataLoader:
    def test_batching(self, synthetic_dataset: Path) -> None:
        dataset = SSRIDataset(synthetic_dataset, split="train")
        loader = create_dataloader(dataset, batch_size=1, shuffle=False)
        batch = next(iter(loader))
        assert batch["features"].shape == (1, CHANNEL_COUNT, 8, 8)
        assert batch["label"].shape == (1, 8, 8)
        assert batch["mask"].shape == (1, 8, 8)

    def test_validation_shuffle_default_false(self, synthetic_dataset: Path) -> None:
        dataset = SSRIDataset(synthetic_dataset, split="validation")
        loader = create_dataloader(dataset)
        first_pass = [batch["sample_id"][0] for batch in loader]
        second_pass = [batch["sample_id"][0] for batch in loader]
        assert first_pass == second_pass == ["sample-b"]

    def test_variable_shape_rejection(self, synthetic_dataset: Path) -> None:
        split_payload = json.loads((synthetic_dataset / "manifest.json").read_text())
        split_payload["splits"]["train"] = ["sample-a", "sample-c"]
        (synthetic_dataset / "manifest.json").write_text(
            json.dumps(split_payload), encoding="utf-8"
        )
        _write_sample(synthetic_dataset / "train" / "sample-c", width=10, height=8)

        dataset = SSRIDataset(synthetic_dataset, split="train")
        loader = create_dataloader(dataset, batch_size=2, shuffle=False)
        with pytest.raises(BatchShapeError):
            next(iter(loader))


class TestIntegrationPipeline:
    def test_dataset_dataloader_batch_contract(self, synthetic_dataset: Path) -> None:
        dataset = SSRIDataset(synthetic_dataset, split="train")
        loader = create_dataloader(dataset, batch_size=1, shuffle=False)
        batch = next(iter(loader))

        assert batch["features"].shape == (1, 13, 8, 8)
        assert batch["label"].shape == (1, 8, 8)
        assert batch["mask"].shape == (1, 8, 8)

        valid = batch["mask"][0].bool()
        valid_features = batch["features"][0][:, valid]
        assert torch.isfinite(valid_features).all()
        assert not torch.isinf(valid_features).any()

    def test_manifest_label_classes_preserved(self, synthetic_dataset: Path) -> None:
        manifest = DatasetManifest.load(synthetic_dataset / "manifest.json")
        assert manifest.label_classes == ("subsidence", "landslide", "sinkhole")

    def test_split_manifest_missing_raises(self, synthetic_dataset: Path) -> None:
        payload = json.loads((synthetic_dataset / "manifest.json").read_text())
        del payload["splits"]["validation"]
        (synthetic_dataset / "manifest.json").write_text(json.dumps(payload), encoding="utf-8")
        with pytest.raises(SplitError):
            SSRIDataset(synthetic_dataset, split="validation")

    def test_missing_statistics_raises(self, synthetic_dataset: Path) -> None:
        (synthetic_dataset / "statistics.json").unlink()
        with pytest.raises(StatisticsError):
            SSRIDataset(synthetic_dataset, split="train")

    def test_label_nodata_preserved(self, synthetic_dataset: Path) -> None:
        sample_dir = synthetic_dataset / "train" / "sample-a"
        grid = _grid_spec()
        label = np.full(grid.shape, FEATURE_NODATA, dtype=np.float32)
        profile = {
            "driver": "GTiff",
            "height": grid.height,
            "width": grid.width,
            "count": 1,
            "dtype": "float32",
            "crs": grid.crs,
            "transform": grid.transform,
            "nodata": FEATURE_NODATA,
        }
        with rasterio.open(sample_dir / "label.tif", "w", **profile) as dataset:
            dataset.write(label, 1)

        dataset = SSRIDataset(synthetic_dataset, split="train")
        sample = dataset[0]
        assert (sample["label"] == LABEL_NODATA).all()
