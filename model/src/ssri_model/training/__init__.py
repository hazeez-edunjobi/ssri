"""SSRI training and optimization system."""

from ssri_model.training.checkpoint import (
    BEST_CHECKPOINT_NAME,
    HISTORY_FILE_NAME,
    LATEST_CHECKPOINT_NAME,
    LEGACY_HISTORY_FILE_NAME,
    load_checkpoint,
    save_checkpoint,
)
from ssri_model.training.config import EarlyStoppingMonitor, LossConfig, TrainingConfig
from ssri_model.training.device import resolve_device
from ssri_model.training.exceptions import (
    CheckpointCompatibilityError,
    CheckpointError,
    DatasetValidationError,
    DeviceNotAvailableError,
    ExperimentExistsError,
    InvalidTrainingConfigError,
    LossComputationError,
    MetricsComputationError,
    NoValidPixelsError,
    SplitLeakageError,
    TrainingError,
)
from ssri_model.training.experiment import (
    CONFIG_FILE_NAME,
    create_experiment_directory,
    generate_experiment_id,
)
from ssri_model.training.history import EpochRecord, TrainingHistory
from ssri_model.training.losses import (
    MaskedCrossEntropyLoss,
    compute_class_weights,
    masked_cross_entropy,
)
from ssri_model.training.metrics import (
    ClassMetrics,
    SegmentationMetrics,
    compute_metrics_from_confusion,
    compute_segmentation_metrics,
    masked_confusion_matrix,
)
from ssri_model.training.optimizer import create_optimizer
from ssri_model.training.reproducibility import set_global_seed
from ssri_model.training.safety import check_split_leakage, validate_training_setup
from ssri_model.training.scheduler import create_scheduler
from ssri_model.training.seed import set_seed
from ssri_model.training.trainer import Trainer, TrainingResult

__all__ = [
    "BEST_CHECKPOINT_NAME",
    "CONFIG_FILE_NAME",
    "CheckpointCompatibilityError",
    "CheckpointError",
    "ClassMetrics",
    "DatasetValidationError",
    "DeviceNotAvailableError",
    "EarlyStoppingMonitor",
    "EpochRecord",
    "ExperimentExistsError",
    "HISTORY_FILE_NAME",
    "InvalidTrainingConfigError",
    "LATEST_CHECKPOINT_NAME",
    "LEGACY_HISTORY_FILE_NAME",
    "LossComputationError",
    "LossConfig",
    "MaskedCrossEntropyLoss",
    "MetricsComputationError",
    "NoValidPixelsError",
    "SegmentationMetrics",
    "SplitLeakageError",
    "Trainer",
    "TrainingConfig",
    "TrainingError",
    "TrainingHistory",
    "TrainingResult",
    "check_split_leakage",
    "compute_class_weights",
    "compute_metrics_from_confusion",
    "compute_segmentation_metrics",
    "create_experiment_directory",
    "create_optimizer",
    "create_scheduler",
    "generate_experiment_id",
    "load_checkpoint",
    "masked_confusion_matrix",
    "masked_cross_entropy",
    "resolve_device",
    "save_checkpoint",
    "set_global_seed",
    "set_seed",
    "validate_training_setup",
]
