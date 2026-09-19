"""Integration tests for Stage 2.2 → 2.3 → 2.4 training pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
import torch
from rasterio.transform import Affine

from ssri_model.architecture import create_ssri_model, SSRIModelConfig
from ssri_model.data.feature_engineering import CHANNEL_ORDER
from ssri_model.data.geophysics import GridSpec
from ssri_model.dataset.catalog import write_manifest
from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.ml.dataloader import create_dataloader
from ssri_model.ml.dataset import SSRIDataset
from ssri_model.ml.splits import DatasetSplit
from ssri_model.ml.statistics_loader import compute_feature_statistics_from_arrays
from ssri_model.training import (
    BEST_CHECKPOINT_NAME,
    Trainer,
    TrainingConfig,
    masked_cross_entropy,
)
from tests.training_helpers import SyntheticSegmentationDataset, make_dataloader


def _grid_spec(width: int = 32, height: int = 32) -> GridSpec:
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
        dataset.write(np.full(grid_spec.shape, value, dtype=np.float32), 1)


def _write_sample(
    sample_dir: Path,
    *,
    width: int = 32,
    height: int = 32,
    channel_offset: float = 0.0,
    label_value: float = 0.0,
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


def _write_training_dataset(root: Path) -> Path:
    root.mkdir(parents=True, exist_ok=True)
    train_ids = [f"train-{index}" for index in range(4)]
    val_ids = [f"val-{index}" for index in range(2)]
    tensors = []
    for index, sample_id in enumerate(train_ids):
        tensors.append(
            _write_sample(
                root / "train" / sample_id,
                label_value=float(index % 3),
                channel_offset=float(index),
            )
        )
    for index, sample_id in enumerate(val_ids):
        _write_sample(
            root / "validation" / sample_id,
            label_value=float(index % 3),
            channel_offset=float(index + 10),
        )

    split = DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=())
    write_manifest(
        root,
        dataset_name="integration",
        version="0.1.0",
        split=split,
        crs="EPSG:32613",
    )
    stats = compute_feature_statistics_from_arrays(tensors)
    statistics_payload = {
        "sample_count": len(train_ids) + len(val_ids),
        "train_count": len(train_ids),
        "validation_count": len(val_ids),
        "test_count": 0,
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
        "label_present_count": len(train_ids) + len(val_ids),
        "created_at": "2026-08-07T09:00:00+00:00",
    }
    (root / "statistics.json").write_text(json.dumps(statistics_payload), encoding="utf-8")
    return root


class TestTrainingIntegration:
    def test_in_memory_pipeline(self, tmp_path: Path) -> None:
        train_dataset = SyntheticSegmentationDataset(num_samples=6, height=32, width=32, seed=10)
        val_dataset = SyntheticSegmentationDataset(num_samples=4, height=32, width=32, seed=11)
        train_loader = make_dataloader(train_dataset, batch_size=2)
        val_loader = make_dataloader(val_dataset, batch_size=2)

        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(
            epochs=2,
            batch_size=2,
            device="cpu",
            checkpoint_dir=str(tmp_path / "checkpoints"),
        )
        trainer = Trainer(model=model, config=config)
        result = trainer.fit(train_loader, val_loader)

        batch = next(iter(train_loader))
        assert batch["features"].dtype == torch.float32
        logits = model(batch["features"])
        assert logits.shape == (batch["features"].shape[0], 3, 32, 32)
        loss = masked_cross_entropy(logits, batch["label"], batch["mask"])
        assert torch.isfinite(loss)
        assert (tmp_path / "checkpoints" / BEST_CHECKPOINT_NAME).exists()
        assert result.final_epoch == 2

    def test_stage22_dataset_pipeline(self, tmp_path: Path) -> None:
        dataset_root = _write_training_dataset(tmp_path / "dataset")
        train_dataset = SSRIDataset(dataset_root, split="train")
        val_dataset = SSRIDataset(dataset_root, split="validation")
        train_loader = create_dataloader(train_dataset, batch_size=2, shuffle=True)
        val_loader = create_dataloader(val_dataset, batch_size=2, shuffle=False)

        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        config = TrainingConfig(
            epochs=2,
            batch_size=2,
            device="cpu",
            checkpoint_dir=str(tmp_path / "checkpoints"),
        )
        trainer = Trainer(model=model, config=config)
        result = trainer.fit(train_loader, val_loader)

        batch = next(iter(train_loader))
        assert batch["features"].shape[1:] == (13, 32, 32)
        logits = model(batch["features"])
        assert logits.shape == (batch["features"].shape[0], 3, 32, 32)
        assert "mask" in batch
        assert result.history.epochs[-1].validation_loss >= 0.0

    def test_mask_not_passed_to_model(self) -> None:
        batch = {
            "features": torch.randn(2, 13, 32, 32, dtype=torch.float32),
            "label": torch.zeros(2, 32, 32, dtype=torch.int64),
            "mask": torch.ones(2, 32, 32, dtype=torch.bool),
        }
        model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
        logits = model(batch["features"])
        assert logits.shape == (2, 3, 32, 32)
