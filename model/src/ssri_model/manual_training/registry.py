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
    # Durable object-storage key (R2/S3). Optional for FS-only local registries.
    object_storage_key: str | None = None
    object_storage_sha256: str | None = None

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
            object_storage_key=(
                str(payload["object_storage_key"])
                if payload.get("object_storage_key")
                else None
            ),
            object_storage_sha256=(
                str(payload["object_storage_sha256"])
                if payload.get("object_storage_sha256")
                else None
            ),
        )


class ModelRegistry:
    """Persists trained model metadata without overwriting prior checkpoints."""

    def __init__(self, storage: TrainingStorage) -> None:
        self.storage = storage
        self._index_path = storage.models_dir / "registry.json"
        self._active_path = storage.models_dir / "active.json"

    def _load_index(self) -> dict[str, Any]:
        if not self._index_path.exists():
            try:
                from ssri_model.storage.durable import ensure_registry_metadata_local

                ensure_registry_metadata_local(self.storage.models_dir)
            except Exception:
                pass
        if not self._index_path.exists():
            return {"models": []}
        return json.loads(self._index_path.read_text(encoding="utf-8"))

    def _save_index(self, payload: dict[str, Any]) -> None:
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        self._index_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        try:
            from ssri_model.storage.durable import mirror_registry_metadata

            mirror_registry_metadata(self.storage.models_dir)
        except Exception:
            pass

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

    def register_uploaded_checkpoint(
        self,
        *,
        model_id: str,
        name: str,
        checkpoint_source: Path | str,
        expected_sha256: str,
        dataset_id: str = "external_bootstrap",
        dataset_name: str = "external_checkpoint",
        notes: str = "",
        training_metrics: dict[str, Any] | None = None,
    ) -> ModelRecord:
        """Register an existing Stage 2.5 ``best.pt`` without retraining.

        Verifies SHA-256 and ``model_config.in_channels == 13``. Does not overwrite
        an existing model_id whose checkpoint bytes differ. Mirrors to object
        storage when the remote backend is configured (production R2).
        """
        import hashlib

        from ssri_model.ml.safe_torch import load_torch_checkpoint

        source = Path(checkpoint_source)
        if not source.is_file():
            raise ModelNotFoundError(f"Checkpoint file was not found: {source}")
        expected = expected_sha256.strip().lower()
        if len(expected) != 64 or any(ch not in "0123456789abcdef" for ch in expected):
            raise UnsafePathError("expected_sha256 must be a 64-character hex digest.")
        digest = hashlib.sha256()
        with source.open("rb") as handle:
            while True:
                chunk = handle.read(1024 * 1024)
                if not chunk:
                    break
                digest.update(chunk)
        actual = digest.hexdigest()
        if actual != expected:
            raise UnsafePathError(
                "Checkpoint SHA-256 does not match the expected digest. "
                "Refusing to register a substituted or corrupted file."
            )
        payload = load_torch_checkpoint(source, map_location="cpu")
        config = payload.get("model_config") or {}
        in_channels = int(config.get("in_channels") or 0)
        if in_channels != 13:
            raise UnsafePathError(
                f"Checkpoint in_channels={in_channels} is incompatible with the "
                "Stage 2.5 13-channel assess contract."
            )
        if "model_state_dict" not in payload:
            raise UnsafePathError("Checkpoint is missing model_state_dict.")

        # Refuse silent replacement of a different artifact under the same id.
        index = self._load_index()
        for item in index.get("models", []):
            if item.get("model_id") != model_id:
                continue
            existing_sha = (item.get("object_storage_sha256") or "").strip().lower()
            existing_path = Path(str(item.get("checkpoint_path") or ""))
            if existing_sha and existing_sha != actual:
                raise UnsafePathError(
                    f"Model '{model_id}' is already registered with a different checkpoint digest."
                )
            if existing_path.is_file():
                existing_digest = hashlib.sha256(existing_path.read_bytes()).hexdigest()
                if existing_digest != actual:
                    raise UnsafePathError(
                        f"Model '{model_id}' is already registered with a different checkpoint file."
                    )

        dest_dir = self.storage.models_dir / model_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_checkpoint = dest_dir / BEST_CHECKPOINT_NAME
        if source.resolve() != dest_checkpoint.resolve():
            shutil.copy2(source, dest_checkpoint)

        record = ModelRecord(
            model_id=model_id,
            name=name,
            created_at=datetime.now(timezone.utc).isoformat(),
            dataset_id=dataset_id,
            dataset_name=dataset_name,
            checkpoint_path=str(dest_checkpoint.resolve()),
            experiment_dir=str(dest_dir.resolve()),
            job_id=None,
            training_metrics=dict(training_metrics or {}),
            evaluation_status="uploaded_checkpoint_only",
            scientific_validation_status="NOT_VALIDATED",
            active=False,
            notes=(
                notes.strip()
                or (
                    "Operator-uploaded Stage 2.5 checkpoint. "
                    "NOT scientifically validated. Weights were not retrained."
                )
            ),
            object_storage_sha256=actual,
        )
        record = self._maybe_mirror_checkpoint(record, dest_checkpoint)
        if not record.object_storage_sha256:
            record.object_storage_sha256 = actual
        models = [item for item in index.get("models", []) if item.get("model_id") != model_id]
        models.append(record.to_dict())
        index["models"] = models
        self._save_index(index)
        return record

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
        record = self._maybe_mirror_checkpoint(record, dest_checkpoint)
        index = self._load_index()
        models = [item for item in index.get("models", []) if item.get("model_id") != model_id]
        models.append(record.to_dict())
        index["models"] = models
        self._save_index(index)
        return record

    def _maybe_mirror_checkpoint(
        self, record: ModelRecord, checkpoint: Path
    ) -> ModelRecord:
        """Best-effort durable mirror for remote object backends; never logs secrets."""
        try:
            from ssri_model.storage.durable import (
                IncompleteObjectStorageConfigError,
                checkpoint_object_key,
                is_remote_object_backend,
                mirror_file_to_object_storage,
            )

            if not is_remote_object_backend():
                return record
            meta = mirror_file_to_object_storage(
                checkpoint,
                checkpoint_object_key(record.model_id, checkpoint.name),
                content_type="application/octet-stream",
            )
            if meta:
                record.object_storage_key = str(meta["object_key"])
                record.object_storage_sha256 = str(meta["sha256"])
        except IncompleteObjectStorageConfigError:
            raise
        except Exception:
            # Local registry remains authoritative; mirror is best-effort unless
            # configuration is explicitly incomplete (raised above).
            pass
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
            # Backward-compatible recovery from durable object storage when FS is empty.
            if model.object_storage_key:
                from ssri_model.storage.durable import resolve_checkpoint_path

                checkpoint = resolve_checkpoint_path(
                    local_path=None,
                    object_key=model.object_storage_key,
                    cache_dir=self.storage.models_dir / model_id / ".object_cache",
                )
                # Persist recovered bytes into the registry tree for subsequent local loads.
                dest = self.storage.models_dir / model_id / BEST_CHECKPOINT_NAME
                dest.parent.mkdir(parents=True, exist_ok=True)
                if checkpoint.resolve() != dest.resolve():
                    shutil.copy2(checkpoint, dest)
                checkpoint = dest
                model.checkpoint_path = str(dest.resolve())
                index = self._load_index()
                models = []
                for item in index.get("models", []):
                    if item.get("model_id") == model_id:
                        item["checkpoint_path"] = model.checkpoint_path
                    models.append(item)
                index["models"] = models
                self._save_index(index)
            else:
                raise ModelNotFoundError(
                    f"Cannot activate model '{model_id}' because its checkpoint is missing."
                )
        # Ensure path stays under training models dir
        try:
            checkpoint.resolve().relative_to(self.storage.models_dir.resolve())
        except ValueError as exc:
            raise UnsafePathError("Checkpoint path is outside the model registry.") from exc
        model = self._maybe_mirror_checkpoint(model, checkpoint)
        # Persist object key if newly mirrored
        index = self._load_index()
        models = []
        for item in index.get("models", []):
            if item.get("model_id") == model_id:
                item["object_storage_key"] = model.object_storage_key
                item["object_storage_sha256"] = model.object_storage_sha256
                item["checkpoint_path"] = model.checkpoint_path
            models.append(item)
        index["models"] = models
        self._save_index(index)
        self._active_path.write_text(
            json.dumps(
                {
                    "model_id": model_id,
                    "checkpoint_path": str(checkpoint.resolve()),
                    "object_storage_key": model.object_storage_key,
                    "object_storage_sha256": model.object_storage_sha256,
                    "activated_at": datetime.now(timezone.utc).isoformat(),
                    "scientific_validation_status": model.scientific_validation_status,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            from ssri_model.storage.durable import mirror_registry_metadata

            mirror_registry_metadata(self.storage.models_dir)
        except Exception:
            pass
        model.active = True
        return model

    def deactivate(self) -> None:
        if self._active_path.exists():
            self._active_path.unlink()
