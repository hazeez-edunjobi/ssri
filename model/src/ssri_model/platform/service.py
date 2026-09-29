"""Dataset registration and training orchestration on top of Stage 2.5."""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path

from ssri_model.manual_training.csv_import import (
    CsvFeatureOnly,
    convert_csv_dataset,
    looks_like_csv_bundle,
)
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.ingest import ingest_zip_bytes
from ssri_model.manual_training.validation import validate_training_dataset
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.runner import run_manual_training
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.platform.models import DatasetVersion, PlatformModel
from ssri_model.platform.store import MemoryPlatformStore, PlatformError

MAX_UPLOAD_BYTES = 500 * 1024 * 1024


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _owned_dataset(store: MemoryPlatformStore, *, dataset_id: str, user_id: str, is_admin: bool):
    dataset = store.get_dataset(dataset_id)
    if dataset is None or (dataset.user_id != user_id and not is_admin):
        raise PlatformError("Dataset not found.", code="NOT_FOUND", status=404)
    if dataset.user_id != user_id and not is_admin:
        raise PlatformError("Dataset not found.", code="NOT_FOUND", status=404)
    return dataset


def register_dataset_zip(
    store: MemoryPlatformStore,
    *,
    output_root: str,
    user_id: str,
    dataset_id: str,
    filename: str,
    content: bytes,
    crs: str = "",
) -> DatasetVersion:
    dataset = store.get_dataset(dataset_id)
    if dataset is None or dataset.user_id != user_id:
        raise PlatformError("Dataset not found.", code="NOT_FOUND", status=404)
    if len(content) > MAX_UPLOAD_BYTES:
        raise PlatformError(
            f"That file is too large. The maximum upload is {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.",
            code="UPLOAD_TOO_LARGE",
            status=400,
        )
    lowered = filename.lower()
    if lowered.endswith(".csv") or looks_like_csv_bundle(filename, content):
        return _register_csv(
            store,
            output_root=output_root,
            user_id=user_id,
            dataset=dataset,
            dataset_id=dataset_id,
            filename=filename,
            content=content,
            crs=crs,
        )
    if not lowered.endswith(".zip"):
        raise PlatformError(
            "Upload a .zip of a Stage 2.5 dataset (manifest.json, statistics.json, train/, validation/). "
            "Screenshots and unsupported survey exports are not training data.",
            code="UNSUPPORTED_UPLOAD",
            status=400,
        )

    storage = TrainingStorage(output_root)
    staging = storage.create_dataset(name=dataset.name, description=dataset.description)
    try:
        _record, preview = ingest_zip_bytes(
            storage,
            staging.dataset_id,
            filename=filename,
            content=content,
        )
    except ManualTrainingError as exc:
        raise PlatformError(exc.message, code=exc.code, status=400) from exc
    version_number = store.next_version_number(dataset_id)
    version_id = str(uuid.uuid4())
    safe_name = _safe_object_name(filename)
    object_path = f"{user_id}/{dataset_id}/{version_id}/{safe_name}"
    upload_object = getattr(store, "upload_dataset_object", None)
    if upload_object is not None:
        upload_object(path=object_path, content=content)
    preview_payload = preview.to_dict()
    preview_payload["extracted_root"] = staging.root_path
    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        version=version_number,
        storage_path=object_path,
        file_name=Path(filename).name,
        file_size=len(content),
        content_sha256=hashlib.sha256(content).hexdigest(),
        crs=preview.crs,
        width=(preview.spatial_size or {}).get("width"),
        height=(preview.spatial_size or {}).get("height"),
        channel_count=preview.channel_count,
        resolution_m=preview.resolution_m,
        validation_status=preview.validation_status,
        validation_errors=list(preview.errors),
        preview=preview_payload,
        created_at=_now(),
    )
    store.add_version(version)
    store.add_activity(
        user_id=user_id,
        action="dataset_uploaded",
        resource_type="dataset_version",
        resource_id=version.id,
        metadata={"name": dataset.name, "version": version.version, "file_name": version.file_name},
    )
    store.add_activity(
        user_id=user_id,
        action="dataset_validated" if preview.validation_status == "passed" else "dataset_validation_failed",
        resource_type="dataset_version",
        resource_id=version.id,
        metadata={"status": preview.validation_status},
    )
    return version


def execute_platform_training(
    store: MemoryPlatformStore,
    *,
    output_root: str,
    run_id: str,
) -> None:
    """Train with the existing Stage 2.5 runner. Never marks a model scientifically validated."""
    run = store.get_run(run_id)
    if run is None:
        return
    if run.status in {"COMPLETED", "FAILED", "CANCELLED"}:
        return
    version = store.get_version(run.dataset_version_id)
    dataset = store.get_dataset(run.dataset_id)
    if version is None or dataset is None:
        run.status = "FAILED"
        run.error_message = "The dataset version for this run is no longer available."
        run.completed_at = _now()
        store.save_run(run)
        return
    if version.validation_status != "passed":
        run.status = "FAILED"
        run.error_message = "Training could not start because the dataset version did not pass validation."
        run.completed_at = _now()
        store.save_run(run)
        store.add_activity(
            user_id=run.user_id,
            action="training_failed",
            resource_type="training_run",
            resource_id=run.id,
            metadata={"name": run.name},
        )
        return

    run.status = "TRAINING"
    run.started_at = run.started_at or _now()
    store.save_run(run)
    storage = TrainingStorage(output_root)
    registry = ModelRegistry(storage)
    try:
        result = run_manual_training(
            storage=storage,
            registry=registry,
            dataset_id=_ensure_manual_dataset(storage, version),
            run_id=f"platform_{run.id[:8]}",
            job_id=run.job_id,
            epochs=1,
            batch_size=2,
            learning_rate=1e-3,
            seed=run.seed,
            model_name=run.name,
            device="cpu",
        )
    except Exception as exc:  # noqa: BLE001
        message = getattr(exc, "message", None) or (
            "Training failed while preparing or fitting the model."
        )
        run.status = "FAILED"
        run.error_message = str(message)
        run.completed_at = _now()
        run.scientific_validation_status = "NOT_VALIDATED"
        store.save_run(run)
        store.add_activity(
            user_id=run.user_id,
            action="training_failed",
            resource_type="training_run",
            resource_id=run.id,
            metadata={"name": run.name},
        )
        return

    run.status = "EVALUATING"
    store.save_run(run)
    metrics = dict(result.get("metrics") or {})
    run.metrics = metrics
    run.status = "COMPLETED"
    run.completed_at = _now()
    run.scientific_validation_status = "NOT_VALIDATED"
    store.save_run(run)
    model = store.add_model(
        PlatformModel(
            id=str(uuid.uuid4()),
            user_id=run.user_id,
            training_run_id=run.id,
            dataset_id=run.dataset_id,
            dataset_version_id=run.dataset_version_id,
            version=store.next_model_version(run.user_id),
            name=str(result.get("model_name") or run.name),
            checkpoint_path=str(result.get("checkpoint_path") or ""),
            metrics=metrics,
            feature_channels=13,
            scientific_validation_status="NOT_VALIDATED",
            created_at=_now(),
        )
    )
    store.add_activity(
        user_id=run.user_id,
        action="training_completed",
        resource_type="training_run",
        resource_id=run.id,
        metadata={"name": run.name, "model_version": model.version},
    )
    store.add_activity(
        user_id=run.user_id,
        action="model_created",
        resource_type="model",
        resource_id=model.id,
        metadata={"version": model.version, "name": model.name},
    )


def _register_csv(
    store: MemoryPlatformStore,
    *,
    output_root: str,
    user_id: str,
    dataset,
    dataset_id: str,
    filename: str,
    content: bytes,
    crs: str,
) -> DatasetVersion:
    storage = TrainingStorage(output_root)
    staging = storage.create_dataset(name=dataset.name, description=dataset.description)
    analysis: dict = {}
    try:
        analysis = convert_csv_dataset(
            Path(staging.root_path),
            filename=filename,
            content=content,
            crs=crs,
            dataset_name=dataset.name,
        )
        preview = validate_training_dataset(staging.root_path)
        status = preview.validation_status
        errors = list(preview.errors)
        extracted = staging.root_path
        crs_value = preview.crs
        width = (preview.spatial_size or {}).get("width")
        height = (preview.spatial_size or {}).get("height")
        channels = preview.channel_count
        resolution = preview.resolution_m
    except CsvFeatureOnly as exc:
        analysis = exc.analysis
        status = "failed"
        errors = [exc.message]
        extracted = ""
        crs_value = analysis.get("crs")
        grid = analysis.get("grid") or {}
        width = grid.get("width")
        height = grid.get("height")
        channels = None
        resolution = analysis.get("x_spacing")
    except ManualTrainingError as exc:
        raise PlatformError(exc.message, code=exc.code, status=400) from exc
    version_id = str(uuid.uuid4())
    safe_name = _safe_object_name(filename)
    object_path = f"{user_id}/{dataset_id}/{version_id}/{safe_name}"
    upload_object = getattr(store, "upload_dataset_object", None)
    if upload_object is not None:
        upload_object(path=object_path, content=content)
    preview_payload = {"csv_analysis": analysis, "extracted_root": extracted}
    version = DatasetVersion(
        id=version_id,
        dataset_id=dataset_id,
        version=store.next_version_number(dataset_id),
        storage_path=object_path,
        file_name=Path(filename).name,
        file_size=len(content),
        content_sha256=hashlib.sha256(content).hexdigest(),
        crs=crs_value,
        width=width,
        height=height,
        channel_count=channels,
        resolution_m=resolution,
        validation_status=status,
        validation_errors=errors,
        preview=preview_payload,
        created_at=_now(),
    )
    store.add_version(version)
    store.add_activity(
        user_id=user_id,
        action="dataset_uploaded",
        resource_type="dataset_version",
        resource_id=version.id,
        metadata={"name": dataset.name, "version": version.version, "file_name": version.file_name, "source_format": "csv"},
    )
    store.add_activity(
        user_id=user_id,
        action="dataset_validated" if status == "passed" else "dataset_validation_failed",
        resource_type="dataset_version",
        resource_id=version.id,
        metadata={"status": status},
    )
    return version


def _safe_object_name(filename: str) -> str:
    name = Path(filename).name.replace("\\", "_").replace("/", "_")
    cleaned = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)
    return cleaned or "dataset.zip"


def _ensure_manual_dataset(storage: TrainingStorage, version: DatasetVersion) -> str:
    """Point a manual-training dataset record at an already extracted Stage 2.5 tree."""
    record = storage.create_dataset(name=f"platform-{version.version}")
    extracted = str((version.preview or {}).get("extracted_root") or "")
    record.root_path = extracted or version.storage_path
    record.validation_status = "passed"
    storage.save_dataset(record)
    return record.dataset_id
