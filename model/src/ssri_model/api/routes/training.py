"""Manual training API routes (no new authentication layer)."""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field

from ssri_model.api.dependencies import (
    get_app_state,
    get_job_executor,
    get_job_service,
    get_service_config,
    require_run_inference,
    require_read_status,
)
from ssri_model.auth.authorization import has_permission
from ssri_model.auth.models import Permission
from ssri_model.api.job_workers import run_training_job
from ssri_model.auth.models import AuthenticatedPrincipal
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.models import JobStatus, JobType
from ssri_model.jobs.service import JobService
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.ingest import ingest_zip_path, register_existing_path
from ssri_model.manual_training.upload_io import cleanup_temp, spool_upload_to_temp
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.manual_training.validation import validate_training_dataset
from ssri_model.service.config import ServiceConfig

router = APIRouter(prefix="/training", tags=["training"])


def _storage(service_config: ServiceConfig) -> TrainingStorage:
    return TrainingStorage(service_config.output_root)


def _registry(service_config: ServiceConfig) -> ModelRegistry:
    return ModelRegistry(_storage(service_config))


def _error_payload(exc: ManualTrainingError) -> dict[str, Any]:
    payload: dict[str, Any] = {"error": {"code": exc.code, "message": exc.message}}
    errors = getattr(exc, "errors", None)
    if errors:
        payload["error"]["details"] = list(errors)
    return payload


class CreateDatasetBody(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    description: str = ""
    hazard_notes: str = Field(
        default="",
        description="Notes about hazards/tasks (Stage 2.5 uses subsidence, landslide, sinkhole).",
    )
    geographic_area: str = ""
    data_source: str = ""
    notes: str = ""


class RegisterPathBody(BaseModel):
    source_path: str = Field(min_length=1)


class StartTrainingBody(BaseModel):
    dataset_id: str
    epochs: int = Field(default=20, ge=1, le=500)
    batch_size: int = Field(default=4, ge=1, le=64)
    learning_rate: float = Field(default=1e-3, gt=0, le=1.0)
    seed: int = Field(default=42, ge=0)
    early_stopping_patience: int | None = Field(default=None, ge=1, le=100)
    model_name: str | None = Field(default=None, max_length=120)
    device: str = Field(default="cpu", pattern="^(auto|cpu|cuda)$")


class ActivateModelBody(BaseModel):
    model_id: str


@router.get("/requirements")
def training_requirements() -> dict[str, Any]:
    """Explain what operators must provide for Stage 2.5 training."""
    return {
        "architecture": "SSRIModel (Stage 2.5 U-Net segmentation)",
        "hazards": ["subsidence", "landslide", "sinkhole"],
        "channels": 13,
        "channel_names": [
            "elevation",
            "slope",
            "plan_curvature",
            "profile_curvature",
            "twi",
            "relative_relief",
            "valley_depth",
            "ndvi",
            "ndwi",
            "clay_mineral_ratio",
            "iron_oxide_index",
            "gravity",
            "magnetics",
        ],
        "required_root_files": ["manifest.json", "statistics.json"],
        "required_sample_files": [
            "feature_stack.npy",
            "label.tif",
            "metadata.json",
        ],
        "recommended_sample_files": ["preview.png"],
        "layout": {
            "train/<sample_id>/": "Training samples",
            "validation/<sample_id>/": "Validation samples (required, non-empty)",
            "test/<sample_id>/": "Optional held-out samples",
        },
        "upload_format": "zip archive of the dataset root",
        "notes": [
            "Successful training produces a checkpoint usable by /api/v1/assess.",
            "Training completion does not equal scientific validation.",
            "New runs never overwrite the previously active assessment checkpoint unless you promote a model.",
        ],
    }


@router.post("/datasets", status_code=201)
def create_dataset(
    body: CreateDatasetBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    storage = _storage(service_config)
    try:
        record = storage.create_dataset(
            name=body.name,
            description=body.description,
            hazard_notes=body.hazard_notes,
            geographic_area=body.geographic_area,
            data_source=body.data_source,
            notes=body.notes,
        )
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content=_error_payload(exc))  # type: ignore[return-value]
    return {"dataset": record.to_dict()}


@router.get("/datasets")
def list_datasets(
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> dict[str, Any]:
    storage = _storage(service_config)
    return {"datasets": [item.to_dict() for item in storage.list_datasets()]}


@router.get("/datasets/{dataset_id}")
def get_dataset(
    dataset_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> dict[str, Any]:
    storage = _storage(service_config)
    try:
        record = storage.get_dataset(dataset_id)
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=404, content=_error_payload(exc))  # type: ignore[return-value]
    return {"dataset": record.to_dict()}


@router.post("/datasets/{dataset_id}/upload")
async def upload_dataset_zip(
    dataset_id: str,
    file: UploadFile = File(...),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    from pathlib import Path

    storage = _storage(service_config)
    tmp_path = None
    try:
        tmp_path, _nbytes = await spool_upload_to_temp(
            file, suffix=Path(file.filename or "dataset.zip").suffix or ".zip"
        )
        record, preview = ingest_zip_path(
            storage,
            dataset_id,
            filename=file.filename or "dataset.zip",
            zip_path=tmp_path,
        )
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        status = 413 if exc.code in {
            "UPLOAD_TOO_LARGE",
            "ZIP_TOO_LARGE_EXPANDED",
            "ZIP_BOMB",
            "ZIP_TOO_MANY_FILES",
        } else 400
        return JSONResponse(status_code=status, content=_error_payload(exc))  # type: ignore[return-value]
    finally:
        cleanup_temp(tmp_path)
    return {
        "dataset": record.to_dict(),
        "preview": preview.to_dict(),
        "validation_status": preview.validation_status,
    }


@router.post("/datasets/{dataset_id}/register-path")
def register_dataset_path(
    dataset_id: str,
    body: RegisterPathBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    storage = _storage(service_config)
    try:
        record, preview = register_existing_path(
            storage, dataset_id, source_path=body.source_path
        )
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content=_error_payload(exc))  # type: ignore[return-value]
    return {
        "dataset": record.to_dict(),
        "preview": preview.to_dict(),
        "validation_status": preview.validation_status,
    }


@router.post("/datasets/{dataset_id}/validate")
def validate_dataset(
    dataset_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    storage = _storage(service_config)
    try:
        record = storage.get_dataset(dataset_id)
        preview = validate_training_dataset(record.root_path)
        record.validation_status = preview.validation_status
        record.validation_errors = list(preview.errors)
        record.preview = preview.to_dict()
        storage.save_dataset(record)
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=404, content=_error_payload(exc))  # type: ignore[return-value]
    return {
        "dataset": record.to_dict(),
        "preview": preview.to_dict(),
        "validation_status": preview.validation_status,
    }


@router.post("/jobs", status_code=202)
def start_training(
    body: StartTrainingBody,
    request: Request,
    service_config: ServiceConfig = Depends(get_service_config),
    job_service: JobService = Depends(get_job_service),
    job_executor: JobExecutor = Depends(get_job_executor),
    principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    storage = _storage(service_config)
    try:
        record = storage.get_dataset(body.dataset_id)
        preview = validate_training_dataset(record.root_path)
        if preview.validation_status != "passed":
            from fastapi.responses import JSONResponse

            return JSONResponse(  # type: ignore[return-value]
                status_code=400,
                content={
                    "error": {
                        "code": "DATASET_VALIDATION_FAILED",
                        "message": (
                            "Training could not start because the dataset failed validation."
                        ),
                        "details": preview.errors,
                    }
                },
            )
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content=_error_payload(exc))  # type: ignore[return-value]

    run_id = f"run_{uuid.uuid4().hex[:12]}"
    request_id = f"train-{run_id}"
    payload = {
        "run_id": run_id,
        "dataset_id": body.dataset_id,
        "epochs": body.epochs,
        "batch_size": body.batch_size,
        "learning_rate": body.learning_rate,
        "seed": body.seed,
        "early_stopping_patience": body.early_stopping_patience,
        "model_name": body.model_name,
        "device": body.device,
        "output_root": service_config.output_root,
    }
    job_record = job_service.create_job(
        request_id=request_id,
        job_type=JobType.TRAINING,
        principal=principal,
        scientific_validation_status="NOT_VALIDATED",
        payload=payload,
    )
    storage.write_progress(
        run_id,
        {
            "phase": "queued",
            "message": "Training job queued.",
            "epoch": 0,
            "total_epochs": body.epochs,
        },
    )
    if job_record.status == JobStatus.QUEUED:
        job_executor.submit(
            job_record.job_id,
            lambda: run_training_job(
                job_service=job_service,
                job_id=job_record.job_id,
                payload=payload,
            ),
        )
    api_prefix = get_app_state(request).api_config.api_prefix
    return {
        "job_id": job_record.job_id,
        "request_id": job_record.request_id,
        "run_id": run_id,
        "status": job_record.status.value,
        "scientific_validation_status": "NOT_VALIDATED",
        "status_url": f"{api_prefix}/training/jobs/{job_record.job_id}",
        "message": (
            "Training job accepted. Completion does not imply scientific validation."
        ),
    }


@router.get("/jobs/{job_id}")
def get_training_job(
    job_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    job_service: JobService = Depends(get_job_service),
    principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> dict[str, Any]:
    from ssri_model.jobs.exceptions import JobAccessDeniedError, JobNotFoundError
    from fastapi.responses import JSONResponse

    try:
        record = job_service.get_job(job_id, principal=principal)
    except (JobNotFoundError, JobAccessDeniedError):
        return JSONResponse(  # type: ignore[return-value]
            status_code=404,
            content={
                "error": {"code": "JOB_NOT_FOUND", "message": "Training job not found."}
            },
        )
    if record.job_type != JobType.TRAINING:
        return JSONResponse(  # type: ignore[return-value]
            status_code=404,
            content={
                "error": {"code": "JOB_NOT_FOUND", "message": "Training job not found."}
            },
        )
    storage = _storage(service_config)
    run_id = str((record.payload or {}).get("run_id") or "")
    progress = storage.read_progress(run_id) if run_id else None
    return {
        "job_id": record.job_id,
        "request_id": record.request_id,
        "job_type": record.job_type.value,
        "status": record.status.value,
        "scientific_validation_status": record.scientific_validation_status,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "result": record.result,
        "progress": progress,
        "payload": {
            "dataset_id": record.payload.get("dataset_id"),
            "epochs": record.payload.get("epochs"),
            "batch_size": record.payload.get("batch_size"),
            "learning_rate": record.payload.get("learning_rate"),
            "seed": record.payload.get("seed"),
            "model_name": record.payload.get("model_name"),
            "run_id": run_id,
        },
    }


def _public_model_payload(model: Any, *, active: bool | None = None) -> dict[str, Any]:
    """Safe metadata for ordinary READ_STATUS callers (no filesystem paths)."""
    return {
        "model_id": model.model_id,
        "name": model.name,
        "created_at": model.created_at,
        "dataset_id": model.dataset_id,
        "dataset_name": model.dataset_name,
        "job_id": model.job_id,
        "evaluation_status": model.evaluation_status,
        "scientific_validation_status": model.scientific_validation_status,
        "active": bool(model.active if active is None else active),
        "notes": model.notes,
        "checkpoint_available": Path(model.checkpoint_path).is_file(),
    }


@router.get("/models")
def list_models(
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> dict[str, Any]:
    registry = _registry(service_config)
    models = registry.list_models()
    if has_permission(principal, Permission.RUN_INFERENCE):
        return {"models": [item.to_dict() for item in models]}
    return {"models": [_public_model_payload(item) for item in models]}


@router.get("/models/active")
def get_active_model(
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> dict[str, Any]:
    registry = _registry(service_config)
    model_id = registry.get_active_model_id()
    reveal_paths = has_permission(principal, Permission.RUN_INFERENCE)
    if not model_id:
        return {
            "active": None,
            "checkpoint_path": None,
            "checkpoint_available": False,
            "model_id": None,
        }
    model = registry.get_model(model_id)
    checkpoint_available = Path(model.checkpoint_path).is_file()
    if reveal_paths:
        return {
            "active": model.to_dict(),
            "checkpoint_path": model.checkpoint_path,
            "checkpoint_available": checkpoint_available,
            "model_id": model.model_id,
        }
    return {
        "active": _public_model_payload(model, active=True),
        "checkpoint_path": None,
        "checkpoint_available": checkpoint_available,
        "model_id": model.model_id,
    }


@router.post("/models/activate")
def activate_model(
    body: ActivateModelBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    registry = _registry(service_config)
    try:
        model = registry.activate(body.model_id)
    except ManualTrainingError as exc:
        from fastapi.responses import JSONResponse

        return JSONResponse(status_code=400, content=_error_payload(exc))  # type: ignore[return-value]
    return {
        "active": model.to_dict(),
        "checkpoint_path": model.checkpoint_path,
        "message": (
            "Model promoted for assessments that use the active checkpoint path. "
            "This does not mark the model as scientifically validated."
        ),
    }


@router.post("/models/deactivate")
def deactivate_model(
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> dict[str, Any]:
    registry = _registry(service_config)
    registry.deactivate()
    return {"active": None, "message": "No active promoted model."}
