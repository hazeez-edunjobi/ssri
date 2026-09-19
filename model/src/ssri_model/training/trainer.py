"""Training loop for the SSRI segmentation model."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import torch
from torch.utils.data import DataLoader

from ssri_model.architecture.model import SSRIModel, count_parameters
from ssri_model.training.checkpoint import (
    BEST_CHECKPOINT_NAME,
    HISTORY_FILE_NAME,
    LATEST_CHECKPOINT_NAME,
    load_checkpoint,
    save_checkpoint,
)
from ssri_model.training.config import EarlyStoppingMonitor, TrainingConfig
from ssri_model.training.experiment import (
    CONFIG_FILE_NAME,
    TRAINING_LOG_NAME,
    config_to_dict,
    create_experiment_directory,
    experiment_config_payload,
    generate_experiment_id,
)
from ssri_model.training.history import EpochRecord, TrainingHistory
from ssri_model.training.losses import compute_class_weights, masked_cross_entropy
from ssri_model.training.metrics import SegmentationMetrics, compute_metrics_from_confusion, masked_confusion_matrix
from ssri_model.training.optimizer import create_optimizer
from ssri_model.training.safety import (
    dataset_manifest_identity,
    validate_training_setup,
)
from ssri_model.training.scheduler import create_scheduler
from ssri_model.training.seed import set_seed
from ssri_model.training.device import resolve_device

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class TrainingResult:
    """Summary returned after a training run."""

    best_epoch: int
    best_validation_loss: float
    best_metric: float
    best_metric_name: str
    final_epoch: int
    stopped_early: bool
    experiment_dir: str
    checkpoint_paths: dict[str, str]
    history: TrainingHistory

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable training result."""
        return {
            "best_epoch": self.best_epoch,
            "best_validation_loss": self.best_validation_loss,
            "best_metric": self.best_metric,
            "best_metric_name": self.best_metric_name,
            "final_epoch": self.final_epoch,
            "stopped_early": self.stopped_early,
            "experiment_dir": self.experiment_dir,
            "checkpoint_paths": dict(self.checkpoint_paths),
            "history": self.history.to_dict(),
        }


def _monitor_is_higher_better(monitor: EarlyStoppingMonitor) -> bool:
    return monitor in ("macro_f1", "mean_iou")


def _metric_value(metrics: SegmentationMetrics, monitor: EarlyStoppingMonitor) -> float:
    if monitor == "macro_f1":
        return metrics.macro_f1
    if monitor == "mean_iou":
        return metrics.mean_iou
    return metrics.accuracy


class Trainer:
    """Mask-aware trainer for the SSRI segmentation model.

    Training uses the train split only. Validation uses the validation split
    only. The test split is never loaded or evaluated by this trainer.
    """

    def __init__(
        self,
        model: SSRIModel,
        config: TrainingConfig,
        *,
        train_loader: DataLoader[dict[str, Any]] | None = None,
        validation_loader: DataLoader[dict[str, Any]] | None = None,
        class_weights: torch.Tensor | None = None,
    ) -> None:
        self.model = model
        self.config = config
        self._train_loader = train_loader
        self._validation_loader = validation_loader
        self.device = resolve_device(config.device)
        self._dataset_identity: dict[str, str] | None = None

        self.class_weights = class_weights
        if self.class_weights is None and config.resolved_class_weights is not None:
            self.class_weights = torch.tensor(
                config.resolved_class_weights,
                dtype=torch.float32,
            )
        if self.class_weights is not None:
            self.class_weights = self.class_weights.to(self.device)

        self.model.to(self.device)
        self.optimizer = create_optimizer(self.model, config)
        self.scheduler = create_scheduler(self.optimizer, config)
        self.history = TrainingHistory()
        self._scaler: torch.cuda.amp.GradScaler | None = None
        if config.mixed_precision and self.device.type == "cuda":
            self._scaler = torch.cuda.amp.GradScaler()

        self._best_metric = float("-inf") if _monitor_is_higher_better(config.early_stopping_monitor) else float("inf")
        self._best_validation_loss = float("inf")
        self._best_epoch = 0
        self._epochs_without_improvement = 0
        self._start_epoch = 1
        self._experiment_dir: Path | None = None

    def fit(
        self,
        train_loader: DataLoader[dict[str, Any]] | None = None,
        validation_loader: DataLoader[dict[str, Any]] | None = None,
    ) -> TrainingResult:
        """Train the model with validation, checkpointing, and optional early stopping."""
        train_loader = train_loader or self._train_loader
        validation_loader = validation_loader or self._validation_loader
        if train_loader is None or validation_loader is None:
            raise ValueError("Both train_loader and validation_loader must be provided")

        self._train_loader = train_loader
        self._validation_loader = validation_loader

        set_seed(self.config.seed)
        self._prepare_experiment()
        assert self._experiment_dir is not None
        self._run_preflight_checks(train_loader)

        if self.config.compute_class_weights_from_train and self.class_weights is None:
            dataset = train_loader.dataset
            if hasattr(dataset, "__getitem__") and hasattr(dataset, "__len__"):
                self.class_weights = compute_class_weights(dataset).to(self.device)
                logger.info("Computed class weights from training split: %s", self.class_weights.tolist())

        latest_path = self._experiment_dir / LATEST_CHECKPOINT_NAME
        best_path = self._experiment_dir / BEST_CHECKPOINT_NAME
        history_path = self._experiment_dir / HISTORY_FILE_NAME

        stopped_early = False
        final_epoch = 0

        for epoch in range(self._start_epoch, self.config.epochs + 1):
            final_epoch = epoch
            epoch_start = time.perf_counter()
            train_loss = self._train_epoch(train_loader)

            validation_loss = float("nan")
            validation_metrics = SegmentationMetrics(
                accuracy=0.0,
                mean_iou=0.0,
                mean_f1=0.0,
                macro_f1=0.0,
                classes={},
                confusion_matrix=((0, 0, 0), (0, 0, 0), (0, 0, 0)),
            )
            if epoch % self.config.validate_every == 0:
                validation_loss, validation_metrics = self._validate_epoch(validation_loader)

            learning_rate = float(self.optimizer.param_groups[0]["lr"])
            epoch_seconds = time.perf_counter() - epoch_start

            record = EpochRecord(
                epoch=epoch,
                train_loss=train_loss,
                validation_loss=validation_loss,
                learning_rate=learning_rate,
                accuracy=validation_metrics.accuracy,
                macro_f1=validation_metrics.macro_f1,
                mean_iou=validation_metrics.mean_iou,
                epoch_seconds=epoch_seconds,
            )
            self.history.add_epoch(record)

            logger.info(
                "epoch=%s train_loss=%.6f validation_loss=%.6f lr=%.6f "
                "macro_f1=%.6f mean_iou=%.6f epoch_seconds=%.2f",
                epoch,
                train_loss,
                validation_loss,
                learning_rate,
                validation_metrics.macro_f1,
                validation_metrics.mean_iou,
                epoch_seconds,
            )

            monitor_value = self._monitor_value(validation_loss, validation_metrics)
            improved = self._is_improved(monitor_value, validation_loss)
            if improved:
                self._best_metric = monitor_value
                self._best_validation_loss = validation_loss
                self._best_epoch = epoch
                self._epochs_without_improvement = 0
                self.history.update_best(
                    epoch=epoch,
                    metric_value=monitor_value,
                    metric_name=self.config.early_stopping_monitor,
                    higher_is_better=_monitor_is_higher_better(
                        self.config.early_stopping_monitor
                    ),
                )
                if epoch % self.config.checkpoint_every == 0 or improved:
                    self._save_checkpoint(best_path, epoch, validation_loss, monitor_value)
                    logger.info(
                        "Saved best checkpoint epoch=%s monitor=%s value=%.6f path=%s",
                        epoch,
                        self.config.early_stopping_monitor,
                        monitor_value,
                        best_path,
                    )
            else:
                self._epochs_without_improvement += 1

            if epoch % self.config.checkpoint_every == 0:
                self._save_checkpoint(latest_path, epoch, validation_loss, monitor_value)

            self.history.save_json(history_path)
            self._step_scheduler(validation_loss)

            if (
                self.config.early_stopping_enabled
                and self.config.early_stopping_patience is not None
                and self._epochs_without_improvement >= self.config.early_stopping_patience
            ):
                stopped_early = True
                logger.info(
                    "Early stopping at epoch=%s monitor=%s patience=%s",
                    epoch,
                    self.config.early_stopping_monitor,
                    self.config.early_stopping_patience,
                )
                break

        logger.info(
            "Training complete experiment=%s best_epoch=%s best_metric=%.6f",
            self._experiment_dir,
            self._best_epoch,
            self._best_metric,
        )

        return TrainingResult(
            best_epoch=self._best_epoch,
            best_validation_loss=self._best_validation_loss,
            best_metric=self._best_metric,
            best_metric_name=self.config.early_stopping_monitor,
            final_epoch=final_epoch,
            stopped_early=stopped_early,
            experiment_dir=str(self._experiment_dir),
            checkpoint_paths={
                "latest": str(latest_path),
                "best": str(best_path),
                "history": str(history_path),
                "config": str(self._experiment_dir / CONFIG_FILE_NAME),
            },
            history=self.history,
        )

    def resume_from_checkpoint(self, checkpoint_path: Path) -> dict[str, Any]:
        """Restore model, optimizer, scheduler, and history from a checkpoint."""
        payload = load_checkpoint(
            checkpoint_path,
            model=self.model,
            optimizer=self.optimizer,
            scheduler=self.scheduler,
            map_location=self.device,
            expected_dataset_identity=self._dataset_identity,
        )
        self.history = TrainingHistory.from_dict(payload.get("training_history", {}))
        self._best_validation_loss = float(payload.get("best_validation_loss", float("inf")))
        self._best_metric = float(payload.get("best_metric", self._best_metric))
        self._best_epoch = int(payload.get("epoch", 0))
        self._start_epoch = self._best_epoch + 1
        if self._experiment_dir is None:
            self._experiment_dir = checkpoint_path.parent
        return payload

    def _prepare_experiment(self) -> None:
        if self.config.checkpoint_dir is not None:
            self._experiment_dir = Path(self.config.checkpoint_dir)
            self._experiment_dir.mkdir(parents=True, exist_ok=True)
            (self._experiment_dir / "logs").mkdir(parents=True, exist_ok=True)
        else:
            experiment_id = self.config.experiment_id or generate_experiment_id(
                seed=self.config.seed
            )
            self._experiment_dir = create_experiment_directory(
                self.config.output_dir,
                experiment_id=experiment_id,
            )

        log_path = self._experiment_dir / "logs" / TRAINING_LOG_NAME
        file_handler = logging.FileHandler(log_path, encoding="utf-8")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )
        logger.addHandler(file_handler)

        if self.config.dataset_manifest is not None:
            manifest = validate_training_setup(
                manifest_path=self.config.dataset_manifest,
                model=self.model,
            )
            self._dataset_identity = dataset_manifest_identity(manifest)

        config_payload = experiment_config_payload(
            training_config=config_to_dict(self.config),
            model_config=config_to_dict(self.model.config),
            dataset_manifest=self._dataset_identity,
            seed=self.config.seed,
            device=str(self.device),
            experiment_id=self._experiment_dir.name,
        )
        (self._experiment_dir / CONFIG_FILE_NAME).write_text(
            __import__("json").dumps(config_payload, indent=2),
            encoding="utf-8",
        )

        summary = count_parameters(self.model)
        logger.info(
            "Experiment start dir=%s device=%s parameters=%s dataset=%s",
            self._experiment_dir,
            self.device,
            summary.total_parameters,
            self._dataset_identity,
        )

    def _run_preflight_checks(self, train_loader: DataLoader[dict[str, Any]]) -> None:
        if self._validation_loader is None:
            raise ValueError("validation_loader must be set before training")
        train_count = len(train_loader.dataset)  # type: ignore[arg-type]
        validation_count = len(self._validation_loader.dataset)  # type: ignore[arg-type]
        logger.info(
            "Training samples=%s validation samples=%s",
            train_count,
            validation_count,
        )

    def _monitor_value(
        self,
        validation_loss: float,
        metrics: SegmentationMetrics,
    ) -> float:
        if self.config.early_stopping_monitor == "validation_loss":
            return validation_loss
        return _metric_value(metrics, self.config.early_stopping_monitor)

    def _is_improved(self, monitor_value: float, validation_loss: float) -> bool:
        if self.config.early_stopping_monitor == "validation_loss":
            return validation_loss < (self._best_validation_loss - self.config.min_delta)
        if _monitor_is_higher_better(self.config.early_stopping_monitor):
            return monitor_value > (self._best_metric + self.config.min_delta)
        return monitor_value < (self._best_metric - self.config.min_delta)

    def _save_checkpoint(
        self,
        path: Path,
        epoch: int,
        validation_loss: float,
        monitor_value: float,
    ) -> None:
        save_checkpoint(
            path=path,
            model=self.model,
            optimizer=self.optimizer,
            scheduler=self.scheduler,
            epoch=epoch,
            best_metric=monitor_value,
            best_metric_name=self.config.early_stopping_monitor,
            best_validation_loss=self._best_validation_loss,
            training_config=self.config,
            model_config=self.model.config,
            history=self.history,
            seed=self.config.seed,
            dataset_manifest=self._dataset_identity,
        )

    def _step_scheduler(self, validation_loss: float) -> None:
        if self.scheduler is None:
            return
        if self.config.scheduler == "reduce_on_plateau":
            self.scheduler.step(validation_loss)  # type: ignore[arg-type]
            return
        self.scheduler.step()

    def _train_epoch(self, train_loader: DataLoader[dict[str, Any]]) -> float:
        self.model.train()
        total_loss = 0.0
        batch_count = 0

        for batch in train_loader:
            features = batch["features"].to(self.device, non_blocking=True)
            labels = batch["label"].to(self.device, non_blocking=True)
            mask = batch["mask"].to(self.device, non_blocking=True)

            self.optimizer.zero_grad(set_to_none=True)

            if self._scaler is not None:
                with torch.cuda.amp.autocast():
                    logits = self.model(features)
                    loss = masked_cross_entropy(
                        logits,
                        labels,
                        mask,
                        class_weights=self.class_weights,
                        num_classes=self.model.num_classes,
                    )
                self._scaler.scale(loss).backward()  # type: ignore[no-untyped-call]
                if self.config.gradient_clip_norm > 0.0:
                    self._scaler.unscale_(self.optimizer)
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.config.gradient_clip_norm,
                    )
                self._scaler.step(self.optimizer)
                self._scaler.update()
            else:
                logits = self.model(features)
                loss = masked_cross_entropy(
                    logits,
                    labels,
                    mask,
                    class_weights=self.class_weights,
                    num_classes=self.model.num_classes,
                )
                loss.backward()  # type: ignore[no-untyped-call]
                if self.config.gradient_clip_norm > 0.0:
                    torch.nn.utils.clip_grad_norm_(
                        self.model.parameters(),
                        self.config.gradient_clip_norm,
                    )
                self.optimizer.step()

            total_loss += float(loss.detach().item())
            batch_count += 1

        if batch_count == 0:
            return 0.0
        return total_loss / float(batch_count)

    def _validate_epoch(
        self,
        validation_loader: DataLoader[dict[str, Any]],
    ) -> tuple[float, SegmentationMetrics]:
        self.model.eval()
        total_loss = 0.0
        batch_count = 0
        confusion = torch.zeros(
            self.model.num_classes,
            self.model.num_classes,
            dtype=torch.int64,
            device=self.device,
        )

        with torch.no_grad():
            for batch in validation_loader:
                features = batch["features"].to(self.device, non_blocking=True)
                labels = batch["label"].to(self.device, non_blocking=True)
                mask = batch["mask"].to(self.device, non_blocking=True)

                if self._scaler is not None:
                    with torch.cuda.amp.autocast():
                        logits = self.model(features)
                        loss = masked_cross_entropy(
                            logits,
                            labels,
                            mask,
                            class_weights=self.class_weights,
                            num_classes=self.model.num_classes,
                        )
                else:
                    logits = self.model(features)
                    loss = masked_cross_entropy(
                        logits,
                        labels,
                        mask,
                        class_weights=self.class_weights,
                        num_classes=self.model.num_classes,
                    )

                predictions = logits.argmax(dim=1)
                batch_confusion = masked_confusion_matrix(
                    predictions,
                    labels,
                    mask,
                    num_classes=self.model.num_classes,
                )
                confusion += batch_confusion.to(self.device)

                total_loss += float(loss.detach().item())
                batch_count += 1

        average_loss = total_loss / float(batch_count) if batch_count else 0.0
        metrics = compute_metrics_from_confusion(confusion.cpu())
        return average_loss, metrics
