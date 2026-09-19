"""Configuration for SSRI test-set evaluation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from ssri_model.evaluation.exceptions import InvalidEvaluationConfigError
from ssri_model.training.config import DeviceType

ScientificValidationStatus = Literal["NOT_VALIDATED", "LIMITED", "VALIDATED"]


@dataclass(frozen=True)
class EvaluationConfig:
    """Typed configuration for held-out test-set evaluation."""

    checkpoint_path: str
    dataset_manifest: str
    output_dir: str

    device: DeviceType = "auto"
    batch_size: int = 4
    num_workers: int = 0

    save_predictions: bool = True
    save_probabilities: bool = False
    save_confidence: bool = False
    generate_report: bool = True

    scientific_validation_status: ScientificValidationStatus = "NOT_VALIDATED"

    def __post_init__(self) -> None:
        if self.batch_size <= 0:
            raise InvalidEvaluationConfigError("batch_size must be greater than zero")
        if self.num_workers < 0:
            raise InvalidEvaluationConfigError("num_workers must be non-negative")
        if self.device not in ("auto", "cpu", "cuda"):
            raise InvalidEvaluationConfigError(f"Unsupported device: {self.device}")
        if self.scientific_validation_status not in (
            "NOT_VALIDATED",
            "LIMITED",
            "VALIDATED",
        ):
            raise InvalidEvaluationConfigError(
                f"Unsupported scientific_validation_status: "
                f"{self.scientific_validation_status}"
            )

    @property
    def checkpoint(self) -> Path:
        """Return the checkpoint path."""
        return Path(self.checkpoint_path)

    @property
    def manifest_path(self) -> Path:
        """Return the dataset manifest path."""
        return Path(self.dataset_manifest)

    @property
    def output_path(self) -> Path:
        """Return the evaluation output directory."""
        return Path(self.output_dir)

    @property
    def dataset_root(self) -> Path:
        """Return the dataset root inferred from the manifest path."""
        return self.manifest_path.parent

    def validate_paths(self) -> None:
        """Validate that required paths exist."""
        if not self.checkpoint.exists():
            raise InvalidEvaluationConfigError(
                f"Checkpoint not found: {self.checkpoint}"
            )
        if not self.manifest_path.exists():
            raise InvalidEvaluationConfigError(
                f"Dataset manifest not found: {self.manifest_path}"
            )
