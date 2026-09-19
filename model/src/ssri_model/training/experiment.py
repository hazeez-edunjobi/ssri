"""Experiment directory management for SSRI training."""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4

from ssri_model.training.exceptions import ExperimentExistsError

CONFIG_FILE_NAME = "config.json"
HISTORY_FILE_NAME = "history.json"
LOG_DIR_NAME = "logs"
TRAINING_LOG_NAME = "training.log"


def generate_experiment_id(*, seed: int | None = None) -> str:
    """Generate a unique experiment identifier."""
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    suffix = uuid4().hex[:8]
    if seed is not None:
        return f"{timestamp}-seed{seed}-{suffix}"
    return f"{timestamp}-{suffix}"


def create_experiment_directory(
    output_dir: Path | str,
    *,
    experiment_id: str | None = None,
    overwrite: bool = False,
) -> Path:
    """Create the standard SSRI experiment directory layout."""
    root = Path(output_dir) / "experiments"
    chosen_id = experiment_id or generate_experiment_id()
    experiment_dir = root / chosen_id

    if experiment_dir.exists() and not overwrite:
        raise ExperimentExistsError(
            f"Experiment directory already exists: {experiment_dir}"
        )

    experiment_dir.mkdir(parents=True, exist_ok=True)
    (experiment_dir / LOG_DIR_NAME).mkdir(parents=True, exist_ok=True)
    return experiment_dir


def save_experiment_config(experiment_dir: Path, payload: dict[str, Any]) -> Path:
    """Persist the serialized experiment configuration."""
    destination = experiment_dir / CONFIG_FILE_NAME
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def experiment_config_payload(
    *,
    training_config: dict[str, Any],
    model_config: dict[str, Any],
    dataset_manifest: dict[str, Any] | None,
    seed: int,
    device: str,
    experiment_id: str,
) -> dict[str, Any]:
    """Build a complete experiment configuration document."""
    return {
        "experiment_id": experiment_id,
        "seed": seed,
        "device": device,
        "training_config": training_config,
        "model_config": model_config,
        "dataset_manifest": dataset_manifest,
    }


def config_to_dict(config: Any) -> dict[str, Any]:
    """Convert a dataclass config to a JSON-serializable dictionary."""
    return asdict(config)
