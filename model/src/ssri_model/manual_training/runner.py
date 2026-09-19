"""Execute Stage 2.5 training for a registered manual-training dataset."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from typing import Any, Callable

from ssri_model.architecture import SSRIModelConfig, create_ssri_model
from ssri_model.manual_training.exceptions import (
    DatasetValidationFailed,
    ManualTrainingError,
)
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.manual_training.validation import validate_training_dataset
from ssri_model.ml.dataloader import create_dataloader
from ssri_model.ml.dataset import SSRIDataset
from ssri_model.training import Trainer, TrainingConfig

logger = logging.getLogger(__name__)


def run_manual_training(
    *,
    storage: TrainingStorage,
    registry: ModelRegistry,
    dataset_id: str,
    run_id: str,
    job_id: str | None = None,
    epochs: int = 20,
    batch_size: int = 4,
    learning_rate: float = 1e-3,
    seed: int = 42,
    early_stopping_patience: int | None = None,
    model_name: str | None = None,
    device: str = "cpu",
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Validate dataset, train SSRIModel, register checkpoint, return result dict."""
    record = storage.get_dataset(dataset_id)
    dataset_root = Path(record.root_path)

    storage.write_progress(
        run_id,
        {
            "phase": "preparing",
            "message": "Validating dataset before training.",
            "epoch": 0,
            "total_epochs": epochs,
        },
    )

    preview = validate_training_dataset(dataset_root)
    if preview.validation_status != "passed":
        raise DatasetValidationFailed(
            "Training could not start because the dataset failed validation.",
            errors=preview.errors,
        )

    run_dir = storage.run_dir(run_id)
    output_dir = run_dir / "experiment"
    output_dir.mkdir(parents=True, exist_ok=True)

    try:
        train_dataset = SSRIDataset(dataset_root, "train")
        val_dataset = SSRIDataset(dataset_root, "validation")
    except Exception as exc:  # noqa: BLE001
        logger.exception("Failed to load SSRIDataset for %s", dataset_id)
        raise ManualTrainingError(
            "Training could not start because the dataset could not be loaded "
            "by the SSRI trainer. Check that samples match the Stage 2.5 layout.",
            code="DATASET_LOAD_FAILED",
        ) from exc

    train_loader = create_dataloader(
        train_dataset, batch_size=batch_size, shuffle=True, num_workers=0
    )
    val_loader = create_dataloader(
        val_dataset, batch_size=batch_size, shuffle=False, num_workers=0
    )

    model = create_ssri_model(SSRIModelConfig())
    config = TrainingConfig(
        output_dir=str(output_dir),
        dataset_manifest=str(dataset_root / "manifest.json"),
        epochs=epochs,
        batch_size=batch_size,
        learning_rate=learning_rate,
        seed=seed,
        device="auto" if device == "auto" else device,  # type: ignore[arg-type]
        early_stopping_patience=early_stopping_patience,
        num_workers=0,
    )

    storage.write_progress(
        run_id,
        {
            "phase": "training",
            "message": "Training in progress.",
            "epoch": 0,
            "total_epochs": epochs,
        },
    )

    def _on_epoch(payload: dict[str, Any]) -> None:
        storage.write_progress(run_id, payload)
        if progress_callback is not None:
            progress_callback(payload)

    trainer = Trainer(model=model, config=config)
    try:
        result = trainer.fit(train_loader, val_loader, epoch_callback=_on_epoch)
    except Exception as exc:  # noqa: BLE001
        logger.exception("Manual training failed for dataset %s", dataset_id)
        raise ManualTrainingError(
            "Training failed while updating model weights. "
            "See server logs for technical details.",
            code="TRAINING_FAILED",
        ) from exc

    model_id = f"ssri-model-{uuid.uuid4().hex[:10]}"
    display_name = model_name or f"{record.name}-{model_id}"
    metrics = {
        "best_epoch": result.best_epoch,
        "best_validation_loss": result.best_validation_loss,
        "best_metric": result.best_metric,
        "best_metric_name": result.best_metric_name,
        "final_epoch": result.final_epoch,
        "stopped_early": result.stopped_early,
        "train_count": preview.train_count,
        "validation_count": preview.validation_count,
    }
    model_record = registry.register_from_training(
        model_id=model_id,
        name=display_name,
        dataset_id=dataset_id,
        dataset_name=record.name,
        experiment_dir=result.experiment_dir,
        job_id=job_id,
        training_metrics=metrics,
    )

    summary = {
        "status": "completed",
        "scientific_validation_status": "NOT_VALIDATED",
        "message": (
            "Training completed successfully. The model is NOT automatically "
            "scientifically validated or production-ready."
        ),
        "dataset_id": dataset_id,
        "dataset_name": record.name,
        "model_id": model_record.model_id,
        "model_name": model_record.name,
        "checkpoint_path": model_record.checkpoint_path,
        "experiment_dir": result.experiment_dir,
        "architecture": "SSRIModel",
        "channels": 13,
        "label_classes": ["subsidence", "landslide", "sinkhole"],
        "metrics": metrics,
        "checkpoint_paths": result.checkpoint_paths,
        "warnings": list(preview.warnings),
    }
    storage.write_progress(
        run_id,
        {
            "phase": "completed",
            "message": summary["message"],
            "epoch": result.final_epoch,
            "total_epochs": epochs,
            "best_epoch": result.best_epoch,
            "best_metric": result.best_metric,
            "model_id": model_record.model_id,
            "checkpoint_path": model_record.checkpoint_path,
        },
    )
    return summary
