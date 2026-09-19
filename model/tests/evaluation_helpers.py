"""Shared helpers for SSRI evaluation tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
import torch
from rasterio.transform import Affine

from ssri_model.architecture import SSRIModelConfig, create_ssri_model
from ssri_model.data.feature_engineering import CHANNEL_ORDER
from ssri_model.data.geophysics import GridSpec
from ssri_model.dataset.catalog import write_manifest
from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.ml.dataloader import create_dataloader
from ssri_model.ml.dataset import SSRIDataset
from ssri_model.ml.splits import DatasetSplit
from ssri_model.ml.statistics_loader import compute_feature_statistics_from_arrays
from ssri_model.training import Trainer, TrainingConfig
from ssri_model.training.checkpoint import save_checkpoint
from ssri_model.training.history import TrainingHistory


def grid_spec(width: int = 16, height: int = 16) -> GridSpec:
    transform = Affine(30.0, 0.0, 500000.0, 0.0, -30.0, 4100000.0)
    return GridSpec(
        crs=rasterio.crs.CRS.from_epsg(32613),
        transform=transform,
        width=width,
        height=height,
        nodata=FEATURE_NODATA,
    )


def write_label(path: Path, spec: GridSpec, value: float = 0.0) -> None:
    profile = {
        "driver": "GTiff",
        "height": spec.height,
        "width": spec.width,
        "count": 1,
        "dtype": "float32",
        "crs": spec.crs,
        "transform": spec.transform,
        "nodata": FEATURE_NODATA,
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(np.full(spec.shape, value, dtype=np.float32), 1)


def write_sample(
    sample_dir: Path,
    *,
    width: int = 16,
    height: int = 16,
    label_value: float = 0.0,
    channel_offset: float = 0.0,
) -> np.ndarray:
    sample_dir.mkdir(parents=True, exist_ok=True)
    spec = grid_spec(width=width, height=height)
    tensor = np.stack(
        [
            np.full((height, width), float(index + 1) + channel_offset, dtype=np.float64)
            for index in range(CHANNEL_COUNT)
        ],
        axis=0,
    )
    np.save(sample_dir / "feature_stack.npy", tensor)
    write_label(sample_dir / "label.tif", spec, value=label_value)
    metadata = {
        "sample_id": sample_dir.name,
        "aoi": {"bbox_wgs84": {"min_lon": -1, "min_lat": 50, "max_lon": 1, "max_lat": 52}},
        "acquisition": {"start_date": "2024-01-01", "end_date": "2024-02-01"},
        "resolution_m": 30.0,
        "crs": str(spec.crs),
        "sources": {"dem": "COP30"},
        "package_version": "0.1.0",
        "created_at": "2026-08-08T09:00:00+00:00",
    }
    (sample_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
    return tensor


def write_evaluation_dataset(root: Path) -> tuple[Path, Path]:
    """Create a synthetic dataset with train, validation, and test splits."""
    root.mkdir(parents=True, exist_ok=True)
    train_ids = ["train-a", "train-b"]
    val_ids = ["val-a"]
    test_ids = ["test-a", "test-b"]
    train_tensors = []
    for index, sample_id in enumerate(train_ids):
        train_tensors.append(
            write_sample(
                root / "train" / sample_id,
                label_value=float(index % 3),
                channel_offset=float(index),
            )
        )
    for index, sample_id in enumerate(val_ids):
        write_sample(
            root / "validation" / sample_id,
            label_value=float(index % 3),
            channel_offset=float(index + 10),
        )
    for index, sample_id in enumerate(test_ids):
        write_sample(
            root / "test" / sample_id,
            label_value=float(index % 3),
            channel_offset=float(index + 20),
        )

    split = DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=tuple(test_ids))
    manifest_path = write_manifest(
        root,
        dataset_name="synthetic-eval",
        version="0.1.0",
        split=split,
        crs="EPSG:32613",
    )
    stats = compute_feature_statistics_from_arrays(train_tensors)
    statistics_payload = {
        "sample_count": len(train_ids) + len(val_ids) + len(test_ids),
        "train_count": len(train_ids),
        "validation_count": len(val_ids),
        "test_count": len(test_ids),
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
        "label_present_count": len(train_ids) + len(val_ids) + len(test_ids),
        "created_at": "2026-08-08T09:00:00+00:00",
    }
    (root / "statistics.json").write_text(json.dumps(statistics_payload), encoding="utf-8")
    return root, manifest_path


def train_and_save_checkpoint(
    dataset_root: Path,
    manifest_path: Path,
    checkpoint_dir: Path,
) -> Path:
    """Train a tiny model and save a checkpoint for evaluation tests."""
    train_ds = SSRIDataset(dataset_root, split="train")
    val_ds = SSRIDataset(dataset_root, split="validation")
    train_loader = create_dataloader(train_ds, batch_size=2, shuffle=True)
    val_loader = create_dataloader(val_ds, batch_size=2, shuffle=False)
    model = create_ssri_model(SSRIModelConfig(base_channels=8, num_encoder_stages=2))
    config = TrainingConfig(
        epochs=1,
        batch_size=2,
        device="cpu",
        checkpoint_dir=str(checkpoint_dir),
        dataset_manifest=str(manifest_path),
    )
    trainer = Trainer(
        model=model,
        config=config,
        train_loader=train_loader,
        validation_loader=val_loader,
    )
    trainer.fit()
    return checkpoint_dir / "best.pt"


def save_manual_checkpoint(
    path: Path,
    *,
    model_config: SSRIModelConfig | None = None,
    dataset_identity: dict[str, str] | None = None,
) -> Path:
    """Save a minimal checkpoint without running training."""
    model = create_ssri_model(model_config or SSRIModelConfig(base_channels=8, num_encoder_stages=2))
    config = TrainingConfig(device="cpu")
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    save_checkpoint(
        path=path,
        model=model,
        optimizer=optimizer,
        scheduler=None,
        epoch=1,
        best_metric=0.5,
        best_metric_name="macro_f1",
        best_validation_loss=0.5,
        training_config=config,
        model_config=model.config,
        history=TrainingHistory(),
        seed=42,
        dataset_manifest=dataset_identity,
    )
    return path
