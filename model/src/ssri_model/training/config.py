"""Training configuration for the SSRI pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.training.exceptions import InvalidTrainingConfigError

OptimizerType = Literal["adam", "adamw", "sgd"]
SchedulerType = Literal["none", "cosine", "reduce_on_plateau"]
DeviceType = Literal["auto", "cpu", "cuda"]
EarlyStoppingMonitor = Literal["macro_f1", "mean_iou", "validation_loss"]


@dataclass(frozen=True)
class LossConfig:
    """Loss-related training options."""

    class_weights: tuple[float, float, float] | None = None
    compute_class_weights_from_train: bool = False

    def __post_init__(self) -> None:
        if self.class_weights is not None and len(self.class_weights) != 3:
            raise InvalidTrainingConfigError(
                "class_weights must contain exactly three values when provided"
            )
        if self.class_weights is not None and any(weight <= 0.0 for weight in self.class_weights):
            raise InvalidTrainingConfigError(
                "class_weights must be strictly positive when provided"
            )


@dataclass(frozen=True)
class TrainingConfig:
    """Typed configuration for SSRI model training and experiments."""

    output_dir: str = "./outputs"
    dataset_manifest: str | None = None
    checkpoint_dir: str | None = None
    experiment_id: str | None = None

    batch_size: int = 4
    num_workers: int = 0
    epochs: int = 20
    learning_rate: float = 1e-3
    weight_decay: float = 1e-4
    optimizer: OptimizerType = "adamw"
    scheduler: SchedulerType = "cosine"
    seed: int = 42
    device: DeviceType = "auto"
    mixed_precision: bool = False
    gradient_clip_norm: float = 1.0
    checkpoint_every: int = 1
    validate_every: int = 1

    early_stopping_patience: int | None = None
    early_stopping_monitor: EarlyStoppingMonitor = "macro_f1"
    min_delta: float = 1e-4

    loss: LossConfig = field(default_factory=LossConfig)
    model_config: SSRIModelConfig | None = None

    class_weights: tuple[float, float, float] | None = None

    def __post_init__(self) -> None:
        if self.epochs <= 0:
            raise InvalidTrainingConfigError("epochs must be greater than zero")
        if self.batch_size <= 0:
            raise InvalidTrainingConfigError("batch_size must be greater than zero")
        if self.learning_rate <= 0.0:
            raise InvalidTrainingConfigError("learning_rate must be greater than zero")
        if self.weight_decay < 0.0:
            raise InvalidTrainingConfigError("weight_decay must be non-negative")
        if self.optimizer not in ("adam", "adamw", "sgd"):
            raise InvalidTrainingConfigError(f"Unsupported optimizer: {self.optimizer}")
        if self.scheduler not in ("none", "cosine", "reduce_on_plateau"):
            raise InvalidTrainingConfigError(f"Unsupported scheduler: {self.scheduler}")
        if self.early_stopping_patience is not None and self.early_stopping_patience <= 0:
            raise InvalidTrainingConfigError(
                "early_stopping_patience must be greater than zero when enabled"
            )
        if self.min_delta < 0.0:
            raise InvalidTrainingConfigError("min_delta must be non-negative")
        if self.gradient_clip_norm < 0.0:
            raise InvalidTrainingConfigError("gradient_clip_norm must be non-negative")
        if self.device not in ("auto", "cpu", "cuda"):
            raise InvalidTrainingConfigError(f"Unsupported device: {self.device}")
        if self.num_workers < 0:
            raise InvalidTrainingConfigError("num_workers must be non-negative")
        if self.checkpoint_every <= 0:
            raise InvalidTrainingConfigError("checkpoint_every must be greater than zero")
        if self.validate_every <= 0:
            raise InvalidTrainingConfigError("validate_every must be greater than zero")
        if self.early_stopping_monitor not in (
            "macro_f1",
            "mean_iou",
            "validation_loss",
        ):
            raise InvalidTrainingConfigError(
                f"Unsupported early_stopping_monitor: {self.early_stopping_monitor}"
            )
        if self.class_weights is not None and len(self.class_weights) != 3:
            raise InvalidTrainingConfigError(
                "class_weights must contain exactly three values when provided"
            )
        if self.class_weights is not None and any(weight <= 0.0 for weight in self.class_weights):
            raise InvalidTrainingConfigError(
                "class_weights must be strictly positive when provided"
            )

    @property
    def resolved_class_weights(self) -> tuple[float, float, float] | None:
        """Return explicit class weights from legacy or nested config."""
        if self.class_weights is not None:
            return self.class_weights
        return self.loss.class_weights

    @property
    def compute_class_weights_from_train(self) -> bool:
        """Return whether class weights should be computed from training data."""
        return self.loss.compute_class_weights_from_train

    @property
    def early_stopping_enabled(self) -> bool:
        """Return True when early stopping is configured."""
        return self.early_stopping_patience is not None

    @property
    def checkpoint_path(self) -> Path:
        """Return the active checkpoint directory."""
        if self.checkpoint_dir is not None:
            return Path(self.checkpoint_dir)
        if self.experiment_id is not None:
            return Path(self.output_dir) / "experiments" / self.experiment_id
        return Path(self.output_dir) / "checkpoints"
