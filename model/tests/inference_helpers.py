"""Shared helpers for SSRI inference tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import rasterio
import torch
from rasterio.transform import Affine

from ssri_model.architecture import SSRIModelConfig, create_ssri_model
from ssri_model.data.geophysics import GridSpec
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.ml.statistics_loader import compute_feature_statistics_from_arrays
from ssri_model.training import TrainingConfig
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


def write_stage1_manifest(
    path: Path,
    *,
    width: int = 16,
    height: int = 16,
    channel_names: tuple[str, ...] | None = None,
) -> GridSpec:
    spec = grid_spec(width=width, height=height)
    names = channel_names or CHANNEL_NAMES
    payload = {
        "package_version": "0.1.0",
        "created_at": "2026-08-08T09:00:00+00:00",
        "crs": str(spec.crs),
        "projection": {
            "transform": list(spec.transform),
            "width": spec.width,
            "height": spec.height,
        },
        "resolution_m": 30.0,
        "channels": [{"index": index + 1, "name": name} for index, name in enumerate(names)],
        "tensor_shape": [CHANNEL_COUNT, height, width],
    }
    path.write_text(json.dumps(payload), encoding="utf-8")
    return spec


def write_feature_stack(
    path: Path,
    *,
    width: int = 16,
    height: int = 16,
    channel_offset: float = 0.0,
    invalid_mask: np.ndarray | None = None,
) -> np.ndarray:
    tensor = np.stack(
        [
            np.full((height, width), float(index + 1) + channel_offset, dtype=np.float64)
            for index in range(CHANNEL_COUNT)
        ],
        axis=0,
    )
    if invalid_mask is not None:
        tensor[:, invalid_mask] = FEATURE_NODATA
    np.save(path, tensor)
    return tensor


def write_statistics(path: Path, tensors: list[np.ndarray]) -> None:
    stats = compute_feature_statistics_from_arrays(tensors)
    payload = {
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
        }
    }
    path.write_text(json.dumps(payload), encoding="utf-8")


def save_inference_checkpoint(
    path: Path,
    *,
    model_config: SSRIModelConfig | None = None,
    dataset_identity: dict[str, str] | None = None,
) -> Path:
    model = create_ssri_model(
        model_config or SSRIModelConfig(base_channels=8, num_encoder_stages=2)
    )
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


def build_inference_inputs(
    root: Path,
    *,
    width: int = 16,
    height: int = 16,
    channel_offset: float = 0.0,
    invalid_mask: np.ndarray | None = None,
) -> tuple[Path, Path, Path, Path, np.ndarray]:
    root.mkdir(parents=True, exist_ok=True)
    feature_path = root / "feature_stack.npy"
    manifest_path = root / "manifest.json"
    statistics_path = root / "statistics.json"
    checkpoint_path = root / "checkpoint.pt"

    tensor = write_feature_stack(
        feature_path,
        width=width,
        height=height,
        channel_offset=channel_offset,
        invalid_mask=invalid_mask,
    )
    write_stage1_manifest(manifest_path, width=width, height=height)
    write_statistics(statistics_path, [tensor])
    save_inference_checkpoint(checkpoint_path)
    return feature_path, manifest_path, statistics_path, checkpoint_path, tensor
