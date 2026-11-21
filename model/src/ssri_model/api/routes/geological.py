"""Geological dataset catalogue API (independent of Stage 2.5 training)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Query, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel, Field

from ssri_model.api.dependencies import (
    get_service_config,
    require_manage_geological,
    require_read_status,
)
from ssri_model.auth.models import AuthenticatedPrincipal
from ssri_model.geological.apply import apply_geological_to_offline_dataset
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.target import resolve_offline_apply_target
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.service.config import ServiceConfig

router = APIRouter(prefix="/geological", tags=["geological"])

# Tenancy model (F4): shared operator catalogue — same pattern as TrainingStorage.
# created_by_key_id is recorded for audit; list/get are not filtered by owner.
GEOLOGICAL_TENANCY_MODEL = "single_tenant_shared_operator_catalogue"


def _storage(config: ServiceConfig) -> GeologicalStorage:
    return GeologicalStorage(config.output_root)


def _service(config: ServiceConfig) -> GeologicalService:
    return GeologicalService(_storage(config))


def _error(exc: ManualTrainingError, status: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


class CreateBody(BaseModel):
    display_name: str = Field(..., min_length=1, max_length=120)
    asset_kind: str = "point_grid_csv"
    description: str = ""
    source_client: str = ""
    notes: str = ""


class DeclareBody(BaseModel):
    measurement_type: str | None = None
    measurement_description: str | None = None
    description: str | None = None
    source_client: str | None = None
    notes: str | None = None
    x_column: str | int | None = None
    y_column: str | int | None = None
    z_column: str | int | None = None
    crs: str | None = None
    working_crs: str | None = None
    units: str | None = None
    z_to_metres: float | None = None
    grid_spacing_units: str | None = None
    nodata_policy: dict[str, Any] | None = None
    provenance: dict[str, Any] | None = None


class ActivationBody(BaseModel):
    activation_status: str
    acknowledged_warnings: list[str] = Field(default_factory=list)


class CoverageBody(BaseModel):
    aoi_bbox: list[float] = Field(..., min_length=4, max_length=4)
    aoi_crs: str | None = None
    measurement_type: str | None = None
    require_validated: bool = True
    require_activated: bool = True


class ApplyBody(BaseModel):
    geo_ids: list[str] = Field(..., min_length=1)
    target_dataset_id: str | None = None
    # Deprecated: accepted only when it matches the registered dataset root.
    target_dataset_root: str | None = None
    window_m: float = 500.0


@router.post("/datasets", status_code=201)
def create_dataset(
    body: CreateBody,
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    try:
        record = _service(service_config).create(
            display_name=body.display_name,
            asset_kind=body.asset_kind,
            description=body.description,
            source_client=body.source_client,
            notes=body.notes,
            created_by_key_id=principal.key_id,
        )
    except ManualTrainingError as exc:
        return _error(exc)
    return {
        "dataset": record.to_dict(),
        "tenancy_model": GEOLOGICAL_TENANCY_MODEL,
    }


@router.get("/datasets")
def list_datasets(
    measurement_type: str | None = None,
    activation_status: str | None = None,
    asset_kind: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    records, total = _storage(service_config).list(
        measurement_type=measurement_type,
        activation_status=activation_status,
        asset_kind=asset_kind,
        limit=limit,
        offset=offset,
    )
    return {
        "datasets": [r.to_dict() for r in records],
        "total": total,
        "limit": limit,
        "offset": offset,
        "tenancy_model": GEOLOGICAL_TENANCY_MODEL,
        "tenancy_note": (
            "Shared operator catalogue: any principal with read_status can list "
            "all geological datasets. created_by_key_id is audit-only."
        ),
    }


@router.get("/datasets/{geo_id}")
def get_dataset(
    geo_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    storage = _storage(service_config)
    try:
        record = storage.get(geo_id)
    except ManualTrainingError as exc:
        return _error(exc, status=404)
    app_status = storage.feature_application_status(record)
    return {
        "dataset": record.to_dict(),
        "inspect": record.inspect_report,
        "validation": record.validation_report,
        "feature_application": app_status,
        "tenancy_model": GEOLOGICAL_TENANCY_MODEL,
    }


@router.post("/datasets/{geo_id}/upload")
async def upload_dataset(
    geo_id: str,
    file: UploadFile = File(...),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    raw = await file.read()
    filename = file.filename or "upload.bin"
    svc = _service(service_config)
    try:
        record = _storage(service_config).get(geo_id)
        if record.asset_kind == "vector_lineament":
            updated = svc.upload_lineament(geo_id, filename=filename, content=raw)
        else:
            updated = svc.upload_csv(geo_id, filename=filename, content=raw)
    except ManualTrainingError as exc:
        status = 413 if exc.code in {"UPLOAD_TOO_LARGE"} else 400
        return _error(exc, status=status)
    return {
        "dataset": updated.to_dict(),
        "inspect": updated.inspect_report,
    }


@router.post("/datasets/{geo_id}/declare")
def declare_metadata(
    geo_id: str,
    body: DeclareBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    payload = body.model_dump(exclude_unset=True)
    try:
        record = _service(service_config).declare(geo_id, payload)
    except ManualTrainingError as exc:
        return _error(exc, status=404 if exc.code == "DATASET_NOT_FOUND" else 400)
    return {"dataset": record.to_dict()}


@router.post("/datasets/{geo_id}/validate")
def validate_dataset(
    geo_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    try:
        record, report = _service(service_config).validate(geo_id)
    except ManualTrainingError as exc:
        return _error(exc)
    status = 200 if report.get("overall") != "FAIL" else 400
    return JSONResponse(
        status_code=status,
        content={"dataset": record.to_dict(), "validation": report},
    )


@router.post("/datasets/{geo_id}/activation")
def set_activation(
    geo_id: str,
    body: ActivationBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    try:
        record = _service(service_config).set_activation(
            geo_id,
            activation_status=body.activation_status,
            acknowledged_warnings=body.acknowledged_warnings,
        )
    except ManualTrainingError as exc:
        return _error(exc)
    return {"dataset": record.to_dict()}


@router.get("/datasets/{geo_id}/original")
def download_original(
    geo_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    storage = _storage(service_config)
    try:
        record = storage.get(geo_id)
        path = storage.original_path(record)
    except ManualTrainingError as exc:
        return _error(exc, status=404)
    if path is None or not path.exists():
        return _error(
            ManualTrainingError("Original file not found.", code="ORIGINAL_MISSING"),
            status=404,
        )
    return FileResponse(
        path,
        filename=record.original_filename or path.name,
        media_type="application/octet-stream",
    )


@router.post("/coverage")
def coverage_query(
    body: CoverageBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    try:
        report = _service(service_config).coverage_query(
            aoi_bbox=body.aoi_bbox,
            aoi_crs=body.aoi_crs,
            measurement_type=body.measurement_type,
            require_validated=body.require_validated,
            require_activated=body.require_activated,
        )
    except (ManualTrainingError, ValueError) as exc:
        message = getattr(exc, "message", str(exc))
        code = getattr(exc, "code", "COVERAGE_ERROR")
        return JSONResponse(
            status_code=400,
            content={"error": {"code": code, "message": message}},
        )
    return {"coverage": report}


@router.post("/apply/offline")
def apply_offline(
    body: ApplyBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Apply catalogue layers onto a registered offline Stage 2.5 dataset (not live assess)."""
    training = TrainingStorage(service_config.output_root)
    try:
        dataset_id, _confined_root = resolve_offline_apply_target(
            training,
            target_dataset_id=body.target_dataset_id,
            target_dataset_root=body.target_dataset_root,
        )
    except ManualTrainingError as exc:
        status = 404 if exc.code == "DATASET_NOT_FOUND" else 400
        return _error(exc, status=status)

    try:
        # Fail-fast resolve above; apply re-resolves by registered id only.
        # HTTP never sets allow_direct_target_root (tests/scripts only).
        report = apply_geological_to_offline_dataset(
            _storage(service_config),
            geo_ids=body.geo_ids,
            target_dataset_id=dataset_id,
            target_dataset_root=body.target_dataset_root,
            window_m=body.window_m,
            record_provenance=True,
        )
    except ManualTrainingError as exc:
        return _error(exc)
    except (ValueError, FileNotFoundError) as exc:
        return JSONResponse(
            status_code=400,
            content={"error": {"code": "APPLY_FAILED", "message": str(exc)}},
        )
    return {"application": report}
