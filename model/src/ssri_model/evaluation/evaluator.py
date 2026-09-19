"""Test-set evaluator for SSRI checkpoints."""

from __future__ import annotations

import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, cast

import torch

from ssri_model import __version__ as package_version
from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.model import SSRIModel
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES
from ssri_model.ml.dataloader import create_dataloader
from ssri_model.ml.dataset import SSRIDataset
from ssri_model.ml.labels import label_class_names
from ssri_model.training.checkpoint import load_checkpoint
from ssri_model.training.losses import build_valid_mask
from ssri_model.training.metrics import masked_confusion_matrix
from ssri_model.training.device import resolve_device

from ssri_model.evaluation.config import EvaluationConfig
from ssri_model.evaluation.exceptions import EvaluationCheckpointError
from ssri_model.evaluation.metrics import (
    compute_evaluation_metrics,
    compute_evaluation_metrics_from_confusion,
)
from ssri_model.evaluation.predictions import (
    logits_to_confidence,
    logits_to_probabilities,
    read_label_grid,
    save_confidence_raster,
    save_prediction_raster,
    save_probability_raster,
)
from ssri_model.evaluation.report import (
    CONFUSION_MATRIX_JSON_NAME,
    EVALUATION_JSON_NAME,
    EVALUATION_MD_NAME,
    SAMPLE_RESULTS_JSON_NAME,
    save_confusion_matrix,
    save_evaluation_json,
    save_evaluation_markdown,
    save_sample_results,
)
from ssri_model.evaluation.safety import validate_evaluation_setup


@dataclass(frozen=True)
class SampleEvaluationResult:
    """Metrics for one evaluated test sample."""

    sample_id: str
    valid_pixel_count: int
    evaluable: bool
    accuracy: float
    macro_f1: float
    mean_iou: float
    per_class_metrics: dict[str, dict[str, float]]

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable sample result."""
        return {
            "sample_id": self.sample_id,
            "valid_pixel_count": self.valid_pixel_count,
            "evaluable": self.evaluable,
            "accuracy": self.accuracy,
            "macro_f1": self.macro_f1,
            "mean_iou": self.mean_iou,
            "per_class_metrics": self.per_class_metrics,
        }


@dataclass
class EvaluationResult:
    """Structured result from a held-out test-set evaluation."""

    dataset_name: str
    dataset_version: str
    checkpoint_path: str
    checkpoint_epoch: int
    checkpoint_metric: float
    checkpoint_metric_name: str
    checkpoint_dataset_identity: dict[str, str] | None
    model_config: dict[str, Any]
    test_sample_count: int
    evaluated_sample_count: int
    unevaluable_sample_count: int
    valid_pixel_count: int
    overall_accuracy: float
    macro_precision: float
    macro_recall: float
    macro_f1: float
    mean_iou: float
    per_class_metrics: dict[str, dict[str, float]]
    confusion_matrix: list[list[int]]
    class_names: tuple[str, ...]
    sample_results: list[SampleEvaluationResult] = field(default_factory=list)
    evaluation_started_at: str = ""
    evaluation_completed_at: str = ""
    evaluation_seconds: float = 0.0
    device: str = "cpu"
    scientific_validation_status: str = "NOT_VALIDATED"
    output_dir: str = ""
    artifact_paths: dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable evaluation result."""
        return {
            "dataset_name": self.dataset_name,
            "dataset_version": self.dataset_version,
            "checkpoint_path": self.checkpoint_path,
            "checkpoint_epoch": self.checkpoint_epoch,
            "checkpoint_metric": self.checkpoint_metric,
            "checkpoint_metric_name": self.checkpoint_metric_name,
            "checkpoint_dataset_identity": self.checkpoint_dataset_identity,
            "model_config": self.model_config,
            "test_sample_count": self.test_sample_count,
            "evaluated_sample_count": self.evaluated_sample_count,
            "unevaluable_sample_count": self.unevaluable_sample_count,
            "valid_pixel_count": self.valid_pixel_count,
            "overall_accuracy": self.overall_accuracy,
            "macro_precision": self.macro_precision,
            "macro_recall": self.macro_recall,
            "macro_f1": self.macro_f1,
            "mean_iou": self.mean_iou,
            "per_class_metrics": self.per_class_metrics,
            "confusion_matrix": {
                "rows": list(self.class_names),
                "columns": list(self.class_names),
                "matrix": self.confusion_matrix,
            },
            "sample_results": [sample.to_dict() for sample in self.sample_results],
            "evaluation_started_at": self.evaluation_started_at,
            "evaluation_completed_at": self.evaluation_completed_at,
            "evaluation_seconds": self.evaluation_seconds,
            "device": self.device,
            "scientific_validation_status": self.scientific_validation_status,
            "channel_count": CHANNEL_COUNT,
            "channel_order": list(CHANNEL_NAMES),
            "package_version": package_version,
            "output_dir": self.output_dir,
            "artifact_paths": dict(self.artifact_paths),
            "save_predictions": self.artifact_paths.get("save_predictions") == "true",
            "save_probabilities": self.artifact_paths.get("save_probabilities") == "true",
            "save_confidence": self.artifact_paths.get("save_confidence") == "true",
        }


def load_evaluation_model(
    checkpoint_path: Path | str,
    *,
    device: torch.device,
    expected_dataset_identity: dict[str, str] | None = None,
) -> tuple[SSRIModel, dict[str, Any]]:
    """Build and load a model from a Stage 2.5 checkpoint."""
    path = Path(checkpoint_path)
    try:
        from ssri_model.ml.safe_torch import load_torch_checkpoint

        payload = load_torch_checkpoint(path, map_location=device)
    except OSError as exc:
        raise EvaluationCheckpointError(f"Failed to load checkpoint: {path}") from exc
    except Exception as exc:
        raise EvaluationCheckpointError(f"Failed to load checkpoint: {path}: {exc}") from exc

    model_config_payload = payload.get("model_config")
    if not isinstance(model_config_payload, dict):
        raise EvaluationCheckpointError("Checkpoint is missing model_config")

    model_config = SSRIModelConfig(**model_config_payload)
    if model_config.in_channels != CHANNEL_COUNT or model_config.num_classes != 3:
        raise EvaluationCheckpointError(
            "Checkpoint model configuration is incompatible with SSRI contract"
        )

    model = SSRIModel(config=model_config)
    try:
        load_checkpoint(
            path,
            model=model,
            map_location=device,
            expected_dataset_identity=expected_dataset_identity,
        )
    except Exception as exc:
        raise EvaluationCheckpointError(str(exc)) from exc

    model.eval()
    return model, payload


class Evaluator:
    """Evaluate a trained SSRI checkpoint on the held-out test split only."""

    def __init__(self, config: EvaluationConfig) -> None:
        self.config = config
        self.device = resolve_device(config.device)

    def evaluate(self) -> EvaluationResult:
        """Run test-set evaluation and write reports/artifacts."""
        started_at = datetime.now(timezone.utc)
        start_time = time.perf_counter()

        manifest = validate_evaluation_setup(self.config)
        expected_identity = {
            "dataset_name": manifest.dataset_name,
            "version": manifest.version,
        }

        model, checkpoint_payload = load_evaluation_model(
            self.config.checkpoint,
            device=self.device,
            expected_dataset_identity=expected_identity,
        )

        test_dataset = SSRIDataset(
            self.config.dataset_root,
            split="test",
        )
        test_loader = create_dataloader(
            test_dataset,
            batch_size=self.config.batch_size,
            shuffle=False,
            num_workers=self.config.num_workers,
        )

        output_dir = self.config.output_path
        predictions_dir = output_dir / "predictions"
        output_dir.mkdir(parents=True, exist_ok=True)

        global_confusion = torch.zeros(3, 3, dtype=torch.int64)
        sample_results: list[SampleEvaluationResult] = []
        evaluated_count = 0
        unevaluable_count = 0

        initial_params = [
            parameter.detach().clone() for parameter in model.parameters()
        ]

        with torch.no_grad():
            for batch in test_loader:
                features = batch["features"].to(self.device)
                labels = batch["label"].to(self.device)
                mask = batch["mask"].to(self.device)
                logits = model(features)

                batch_confusion = masked_confusion_matrix(
                    logits.argmax(dim=1),
                    labels,
                    mask,
                    num_classes=model.num_classes,
                )
                global_confusion += batch_confusion.cpu()

                batch_size = features.shape[0]
                for index in range(batch_size):
                    sample_id = batch["sample_id"][index]
                    sample_logits = logits[index : index + 1]
                    sample_labels = labels[index : index + 1]
                    sample_mask = mask[index : index + 1]
                    valid = build_valid_mask(
                        sample_labels[0],
                        sample_mask[0],
                        num_classes=model.num_classes,
                    )
                    valid_count = int(valid.sum().item())

                    if valid_count == 0:
                        unevaluable_count += 1
                        sample_results.append(
                            SampleEvaluationResult(
                                sample_id=sample_id,
                                valid_pixel_count=0,
                                evaluable=False,
                                accuracy=0.0,
                                macro_f1=0.0,
                                mean_iou=0.0,
                                per_class_metrics={},
                            )
                        )
                        continue

                    evaluated_count += 1
                    sample_metrics = compute_evaluation_metrics(
                        sample_logits,
                        sample_labels,
                        sample_mask,
                        num_classes=model.num_classes,
                    )
                    sample_results.append(
                        SampleEvaluationResult(
                            sample_id=sample_id,
                            valid_pixel_count=sample_metrics.valid_pixel_count,
                            evaluable=True,
                            accuracy=sample_metrics.accuracy,
                            macro_f1=sample_metrics.macro_f1,
                            mean_iou=sample_metrics.mean_iou,
                            per_class_metrics={
                                name: {
                                    "precision": metrics.precision,
                                    "recall": metrics.recall,
                                    "f1": metrics.f1,
                                    "iou": metrics.iou,
                                }
                                for name, metrics in sample_metrics.classes.items()
                            },
                        )
                    )

                    if (
                        self.config.save_predictions
                        or self.config.save_probabilities
                        or self.config.save_confidence
                    ):
                        sample_dir = self.config.dataset_root / "test" / sample_id
                        grid = read_label_grid(sample_dir / "label.tif")
                        sample_predictions = sample_logits.argmax(dim=1)[0]
                        sample_valid = sample_mask[0]

                        if self.config.save_predictions:
                            save_prediction_raster(
                                predictions_dir / sample_id / "prediction.tif",
                                sample_predictions,
                                valid_mask=sample_valid,
                                grid=grid,
                            )
                        if self.config.save_probabilities:
                            save_probability_raster(
                                predictions_dir / sample_id / "probabilities.tif",
                                logits_to_probabilities(sample_logits)[0],
                                valid_mask=sample_valid,
                                grid=grid,
                            )
                        if self.config.save_confidence:
                            save_confidence_raster(
                                predictions_dir / sample_id / "confidence.tif",
                                logits_to_confidence(sample_logits)[0],
                                valid_mask=sample_valid,
                                grid=grid,
                            )

        for before, after in zip(initial_params, model.parameters(), strict=True):
            if not torch.equal(before, after.to(before.device)):
                raise EvaluationCheckpointError(
                    "Model parameters changed during evaluation"
                )

        overall = compute_evaluation_metrics_from_confusion(global_confusion)
        completed_at = datetime.now(timezone.utc)
        elapsed = time.perf_counter() - start_time

        result = EvaluationResult(
            dataset_name=manifest.dataset_name,
            dataset_version=manifest.version,
            checkpoint_path=str(self.config.checkpoint),
            checkpoint_epoch=int(checkpoint_payload.get("epoch", 0)),
            checkpoint_metric=float(checkpoint_payload.get("best_metric", 0.0)),
            checkpoint_metric_name=str(
                checkpoint_payload.get("best_metric_name", "unknown")
            ),
            checkpoint_dataset_identity=checkpoint_payload.get("dataset_manifest"),
            model_config=asdict(model.config),
            test_sample_count=len(test_dataset),
            evaluated_sample_count=evaluated_count,
            unevaluable_sample_count=unevaluable_count,
            valid_pixel_count=overall.valid_pixel_count,
            overall_accuracy=overall.accuracy,
            macro_precision=overall.macro_precision,
            macro_recall=overall.macro_recall,
            macro_f1=overall.macro_f1,
            mean_iou=overall.mean_iou,
            per_class_metrics={
                name: {
                    "precision": metrics.precision,
                    "recall": metrics.recall,
                    "f1": metrics.f1,
                    "iou": metrics.iou,
                }
                for name, metrics in overall.classes.items()
            },
            confusion_matrix=[list(row) for row in overall.confusion_matrix],
            class_names=label_class_names(),
            sample_results=sample_results,
            evaluation_started_at=started_at.isoformat(),
            evaluation_completed_at=completed_at.isoformat(),
            evaluation_seconds=elapsed,
            device=str(self.device),
            scientific_validation_status=self.config.scientific_validation_status,
            output_dir=str(output_dir),
            artifact_paths={
                "save_predictions": str(self.config.save_predictions).lower(),
                "save_probabilities": str(self.config.save_probabilities).lower(),
                "save_confidence": str(self.config.save_confidence).lower(),
            },
        )

        if self.config.generate_report:
            payload = result.to_dict()
            save_evaluation_json(output_dir / EVALUATION_JSON_NAME, payload)
            save_evaluation_markdown(output_dir / EVALUATION_MD_NAME, payload)
            save_confusion_matrix(
                output_dir / CONFUSION_MATRIX_JSON_NAME,
                payload["confusion_matrix"],
            )
            save_sample_results(
                output_dir / SAMPLE_RESULTS_JSON_NAME,
                payload["sample_results"],
            )
            result.artifact_paths.update(
                {
                    "evaluation_json": str(output_dir / EVALUATION_JSON_NAME),
                    "evaluation_md": str(output_dir / EVALUATION_MD_NAME),
                    "confusion_matrix_json": str(output_dir / CONFUSION_MATRIX_JSON_NAME),
                    "sample_results_json": str(output_dir / SAMPLE_RESULTS_JSON_NAME),
                }
            )

        return result


def evaluate_checkpoint(config: EvaluationConfig) -> EvaluationResult:
    """Convenience wrapper for test-set evaluation."""
    return Evaluator(config).evaluate()
