"""Checkpoint loading for SSRI inference."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import torch

from ssri_model.architecture.model import SSRIModel
from ssri_model.evaluation.evaluator import load_evaluation_model
from ssri_model.inference.exceptions import InferenceCheckpointError


def load_inference_checkpoint(
    checkpoint_path: Path | str,
    *,
    device: torch.device,
    expected_dataset_identity: dict[str, str] | None = None,
) -> tuple[SSRIModel, dict[str, Any]]:
    """Load a trained SSRI model from a Stage 2.5 checkpoint."""
    try:
        return load_evaluation_model(
            checkpoint_path,
            device=device,
            expected_dataset_identity=expected_dataset_identity,
        )
    except Exception as exc:
        raise InferenceCheckpointError(str(exc)) from exc
