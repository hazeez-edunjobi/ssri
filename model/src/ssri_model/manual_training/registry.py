"""Model registry for manually trained Stage 2.5 checkpoints."""

from __future__ import annotations

import json
import shutil
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ssri_model.manual_training.exceptions import ModelNotFoundError, UnsafePathError
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.training.checkpoint import BEST_CHECKPOINT_NAME


@dataclass
class ModelRecord:
    model_id: str
    name: str
    created_at: str
    dataset_id: str
    dataset_name: str
    checkpoint_path: str
    experiment_dir: str
    job_id: str | None
    training_metrics: dict[str, Any] = field(default_factory=dict)
    evaluation_status: str = "not_run"
    scientific_validation_status: str = "NOT_VALIDATED"
    active: bool = False
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> ModelRecord:
        return cls(
            model_id=str(payload["model_id"]),
            name=str(payload["name"]),
            created_at=str(payload["created_at"]),
            dataset_id=str(payload["dataset_id"]),
            dataset_name=str(payload.get("dataset_name", "")),
            checkpoint_path=str(payload["checkpoint_path"]),
            experiment_dir=str(payload.get("experiment_dir", "")),
            job_id=payload.get("job_id"),
            training_metrics=dict(payload.get("training_metrics") or {}),
            evaluation_status=str(payload.get("evaluation_status", "not_run")),
            scientific_validation_status=str(
                payload.get("scientific_validation_status", "NOT_VALIDATED")
            ),
            active=bool(payload.get("active", False)),
            notes=str(payload.get("notes", "")),
        )


class ModelRegistry:
    """Persists trained model metadata without overwriting prior checkpoints."""

    def __init__(self, storage: TrainingStorage) -> None:
        self.storage = storage
        self._index_path = storage.models_dir / "registry.json"
        self._active_path = storage.models_dir / "active.json"

    def _load_index(self) -> dict[str, Any]:
        if not self._index_path.exists():
            return {"models": []}
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def _save_index(self, payload: dict[str, Any]) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def list_models(self) -> list[ModelRecord]:
        active_id = self.get_active_model_id()
        models = [
            ModelRecord.from_dict(item) for item in self._load_index().get("models", [])
        ]
        for model in models:
            model.active = model.model_id == active_id
        return models

    def get_model(self, model_id: str) -> ModelRecord:
        for model in self.list_models():
            if model.model_id == model_id:
                return model
        raise ModelNotFoundError(f"Model not found: {model_id}")

    def register_from_training(
        self,
        *,
        model_id: str,
        name: str,
        dataset_id: str,
        dataset_name: str,
        experiment_dir: Path | str,
        job_id: str | None,
        training_metrics: dict[str, Any],
    ) -> ModelRecord:
        experiment = Path(experiment_dir)
        best = experiment / BEST_CHECKPOINT_NAME
        if not best.exists():
            raise ModelNotFoundError(
                f"Training finished but best checkpoint was not found at {best}."
            )
        # Copy into models registry so experiment cleanup cannot orphan the artifact
        dest_dir = self.storage.models_dir / model_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_checkpoint = dest_dir / BEST_CHECKPOINT_NAME
        shutil.copy2(best, dest_checkpoint)
        latest = experiment / "latest.pt"
        if latest.exists():
            shutil.copy2(latest, dest_dir / "latest.pt")

        record = ModelRecord(
            model_id=model_id,
            name=name,
            created_at=datetime.now(timezone.utc).isoformat(),
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            checkpoint_path=str(dest_checkpoint.resolve()),
            experiment_dir=str(experiment.resolve()),
            job_id=job_id,
            training_metrics=training_metrics,
            evaluation_status="training_metrics_only",
            scientific_validation_status="NOT_VALIDATED",
            active=False,
            notes=(
                "Training completed successfully. This does not mean the model is "
                "scientifically validated or production-ready."
            ),
        )
        index = self._load_index()
        models = [item for item in index.get("models", []) if item.get("model_id") != model_id]
        models.append(record.to_dict())
        index["models"] = models
        self._save_index(index)
        return record

    def get_active_model_id(self) -> str | None:
        if not self._active_path.exists():
            return None
        payload = json.loads(self._active_path.read_text(encoding="utf-8"))
        return payload.get("model_id")

    def get_active_checkpoint(self) -> str | None:
        model_id = self.get_active_model_id()
        if not model_id:
            return None
        return self.get_model(model_id).checkpoint_path

    def activate(self, model_id: str) -> ModelRecord:
        model = self.get_model(model_id)
        checkpoint = Path(model.checkpoint_path)
        if not checkpoint.exists():
            raise ModelNotFoundError(
                f"Cannot activate model '{model_id}' because its checkpoint is missing."
            )
        # Ensure path stays under training models dir
        try:
            checkpoint.resolve().relative_to(self.storage.models_dir.resolve())
        except ValueError as exc:
            raise UnsafePathError("Checkpoint path is outside the model registry.") from exc
        self._active_path.write_text(
            json.dumps(
                {
                    "model_id": model_id,
                    "checkpoint_path": str(checkpoint.resolve()),
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        model.active = True
        return model

    def deactivate(self) -> None:
        if self._active_path.exists():
            self._active_path.unlink()
