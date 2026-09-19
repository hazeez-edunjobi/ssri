"""Checkpoint save and load utilities for SSRI training."""

from __future__ import annotations

from dataclasses import asdict
from pathlib import Path
from typing import Any, cast

import torch
import torch.nn as nn

from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.model import SSRIModel
from ssri_model.training.config import TrainingConfig
from ssri_model.training.exceptions import CheckpointCompatibilityError, CheckpointError
from ssri_model.training.history import TrainingHistory


LATEST_CHECKPOINT_NAME = "latest.pt"
BEST_CHECKPOINT_NAME = "best.pt"
HISTORY_FILE_NAME = "history.json"
LEGACY_HISTORY_FILE_NAME = "training_history.json"


def _config_to_dict(config: TrainingConfig | SSRIModelConfig) -> dict[str, Any]:
    return asdict(config)


def _atomic_torch_save(payload: dict[str, Any], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        torch.save(payload, temporary_path)
        temporary_path.replace(path)
    except OSError as exc:
        if temporary_path.exists():
            temporary_path.unlink(missing_ok=True)
        raise CheckpointError(f"Failed to save checkpoint to {path}") from exc


def save_checkpoint(
    *,
    path: Path,
    model: nn.Module,
    optimizer: torch.optim.Optimizer,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None,
    epoch: int,
    best_metric: float,
    best_metric_name: str,
    best_validation_loss: float,
    training_config: TrainingConfig,
    model_config: SSRIModelConfig,
    history: TrainingHistory,
    seed: int,
    dataset_manifest: dict[str, str] | None = None,
) -> None:
    """Save a training checkpoint atomically."""
    payload = {
        "model_state_dict": model.state_dict(),
        "optimizer_state_dict": optimizer.state_dict(),
        "scheduler_state_dict": scheduler.state_dict() if scheduler is not None else None,
        "epoch": epoch,
        "best_metric": best_metric,
        "best_metric_name": best_metric_name,
        "best_validation_loss": best_validation_loss,
        "training_config": _config_to_dict(training_config),
        "model_config": _config_to_dict(model_config),
        "dataset_manifest": dataset_manifest,
        "training_history": history.to_dict(),
        "seed": seed,
    }
    _atomic_torch_save(payload, path)


def _validate_model_config(
    checkpoint_config: dict[str, Any],
    model: SSRIModel,
) -> None:
    expected = model.config
    received_in_channels = int(checkpoint_config.get("in_channels", -1))
    received_num_classes = int(checkpoint_config.get("num_classes", -1))
    if received_in_channels != expected.in_channels:
        raise CheckpointCompatibilityError(
            "Checkpoint in_channels mismatch: "
            f"expected {expected.in_channels}, received {received_in_channels}"
        )
    if received_num_classes != expected.num_classes:
        raise CheckpointCompatibilityError(
            "Checkpoint num_classes mismatch: "
            f"expected {expected.num_classes}, received {received_num_classes}"
        )


def _validate_dataset_identity(
    checkpoint_identity: dict[str, Any] | None,
    expected_identity: dict[str, str] | None,
) -> None:
    if expected_identity is None or checkpoint_identity is None:
        return
    for key in ("dataset_name", "version"):
        if checkpoint_identity.get(key) != expected_identity.get(key):
            raise CheckpointCompatibilityError(
                f"Checkpoint dataset {key} mismatch: "
                f"expected {expected_identity.get(key)!r}, "
                f"received {checkpoint_identity.get(key)!r}"
            )


def load_checkpoint(
    path: Path,
    *,
    model: SSRIModel,
    optimizer: torch.optim.Optimizer | None = None,
    scheduler: torch.optim.lr_scheduler.LRScheduler | None = None,
    map_location: str | torch.device = "cpu",
    expected_dataset_identity: dict[str, str] | None = None,
) -> dict[str, Any]:
    """Load a checkpoint and optionally restore optimizer and scheduler state."""
    if not path.exists():
        raise CheckpointError(f"Checkpoint not found: {path}")

    try:
        from ssri_model.ml.safe_torch import load_torch_checkpoint

        payload = load_torch_checkpoint(path, map_location=map_location)
    except OSError as exc:
        raise CheckpointError(f"Failed to load checkpoint from {path}") from exc
    except Exception as exc:
        raise CheckpointError(f"Failed to load checkpoint from {path}: {exc}") from exc

    model_config = payload.get("model_config")
    if not isinstance(model_config, dict):
        raise CheckpointCompatibilityError(
            "Checkpoint is missing a valid model_config section"
        )
    _validate_model_config(model_config, model)

    dataset_manifest = payload.get("dataset_manifest")
    if isinstance(dataset_manifest, dict):
        _validate_dataset_identity(dataset_manifest, expected_dataset_identity)

    model.load_state_dict(payload["model_state_dict"])

    if optimizer is not None and payload.get("optimizer_state_dict") is not None:
        optimizer.load_state_dict(payload["optimizer_state_dict"])

    if scheduler is not None and payload.get("scheduler_state_dict") is not None:
        scheduler.load_state_dict(payload["scheduler_state_dict"])

    return payload
