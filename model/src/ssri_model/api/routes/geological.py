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
from ssri_model.geological.durable import build_geological_storage
from ssri_model.geological.service import GeologicalService
from ssri_model.geological.storage import GeologicalStorage
from ssri_model.geological.target import resolve_offline_apply_target
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.service.config import ServiceConfig
from ssri_model.service.exceptions import InvalidServiceConfigError

router = APIRouter(prefix="/geological", tags=["geological"])

# Tenancy model (F4): shared operator catalogue — same pattern as TrainingStorage.
# created_by_key_id is recorded for audit; list/get are not filtered by owner.
GEOLOGICAL_TENANCY_MODEL = "single_tenant_shared_operator_catalogue"


def _storage(config: ServiceConfig) -> GeologicalStorage:
    return build_geological_storage(config.output_root)


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
    # Optional survey provenance — omitted fields stay unknown (never fabricated).
    survey_date: str | None = None
    survey_method: str | None = None
    sampling_spacing: str | None = None
    processing_history: str | None = None
    source_organization: str | None = None
    geographic_coverage: str | None = None
    # Apply owner-authoritative Abeokuta TMI column/CRS defaults without re-prompting.
    apply_abeokuta_tmi_preset: bool = False


class ActivationBody(BaseModel):
    activation_status: str
    acknowledged_warnings: list[str] = Field(default_factory=list)


class ProcessTmiBody(BaseModel):
    resolution: float = Field(..., gt=0, description="Grid cell size in CRS units")
    nodata: float = -9999.0


class MagneticOperationBody(BaseModel):
    operation: str = Field(
        ...,
        description=(
            "One of: tmi, rte, gaussian, analytic_signal, "
            "first_vertical_derivative, first_horizontal_derivative, "
            "tilt_derivative, radially_averaged_power_spectrum"
        ),
    )
    resolution: float | None = Field(
        default=None, description="Optional grid spacing (metres) if base grid missing"
    )
    nodata: float = -9999.0
    inclination_deg: float | None = None
    declination_deg: float | None = None
    average_igrf_nT: float | None = None
    gaussian_central_wavelength_m: float | None = None
    gaussian_std: float | None = None
    gaussian_mode: str | None = Field(
        default=None, description="low_pass (default) or high_pass residual"
    )
    rte_amplitude_clip: float | None = Field(
        default=None,
        description="Implementation stabilisation clip (not a publication parameter)",
    )


class LineamentExtractBody(BaseModel):
    percentile: float = Field(92.0, ge=50.0, le=99.9)
    min_length_cells: int = Field(4, ge=2, le=50)
    min_component_cells: int = Field(6, ge=3, le=200)
    density_window_m: float = Field(500.0, gt=0)
    use_residual_blend: bool = True
    ensure_derivatives: bool = True
    nodata: float = -9999.0


class CompatibilityBody(BaseModel):
    decision: str
    notes: str = ""


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
        "processing": record.processing_report,
        "feature_compatibility": record.feature_compatibility,
        "feature_application": app_status,
        "tenancy_model": GEOLOGICAL_TENANCY_MODEL,
        "storage_backend": "filesystem_private_under_output_root",
        "storage_note": (
            "Geological originals are stored under the API output root "
            "(not Supabase Storage / not Cloudinary). "
            "Platform training zips may use Supabase; geospatial catalogue does not."
        ),
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


@router.get("/presets/abeokuta-tmi")
def abeokuta_tmi_preset(
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Return publication-guided Abeokuta Sheet 260 TMI metadata.

    X=easting, Y=northing, Z=TMI; source EPSG:32632; processing EPSG:32631;
    display EPSG:4326.
    """
    from ssri_model.geological.abeokuta_tmi import AUTHORITATIVE_ABEOKUTA_TMI

    return {"preset": AUTHORITATIVE_ABEOKUTA_TMI}


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


@router.get("/datasets/{geo_id}/preview")
def preview_dataset(
    geo_id: str,
    max_points: int = Query(default=5000, ge=100, le=20000),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Sampled TMI preview: WGS84 GeoJSON when eligible, else survey-local scatter."""
    try:
        preview = _service(service_config).preview_tmi(geo_id, max_points=max_points)
    except ManualTrainingError as exc:
        return _error(exc, status=404 if exc.code == "DATASET_NOT_FOUND" else 400)
    return {"geo_id": geo_id, "preview": preview}


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


@router.post("/datasets/{geo_id}/process")
def process_dataset(
    geo_id: str,
    body: ProcessTmiBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Grid validated TMI points to a derived GeoTIFF (original preserved)."""
    try:
        record, report = _service(service_config).process_tmi(
            geo_id, resolution=body.resolution, nodata=body.nodata
        )
    except ManualTrainingError as exc:
        return _error(exc)
    return {
        "dataset": record.to_dict(),
        "processing": report,
        "feature_compatibility": record.feature_compatibility,
    }


@router.get("/conditioning-factors")
def list_conditioning_factors(
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    """Honest inventory of geological conditioning factor availability."""
    from ssri_model.geological.conditioning_inventory import conditioning_factor_inventory

    return conditioning_factor_inventory()


@router.get("/datasets/{geo_id}/magnetic")
def list_magnetic(
    geo_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """List magnetic processing products, history, and CRS roles."""
    try:
        return _service(service_config).list_magnetic_products(geo_id)
    except ManualTrainingError as exc:
        return _error(exc, status=404 if exc.code == "DATASET_NOT_FOUND" else 400)


@router.post("/datasets/{geo_id}/magnetic")
def run_magnetic(
    geo_id: str,
    body: MagneticOperationBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Run one publication-guided magnetic operation (explicit parameters recorded)."""
    param_keys = (
        "inclination_deg",
        "declination_deg",
        "average_igrf_nT",
        "gaussian_central_wavelength_m",
        "gaussian_std",
        "gaussian_mode",
        "rte_amplitude_clip",
    )
    overrides = {
        k: getattr(body, k) for k in param_keys if getattr(body, k) is not None
    }
    try:
        record, report = _service(service_config).run_magnetic_operation(
            geo_id,
            operation=body.operation,
            params=overrides,
            resolution=body.resolution,
            nodata=body.nodata,
        )
    except ManualTrainingError as exc:
        return _error(exc)
    return {"dataset": record.to_dict(), "magnetic": report}


@router.post("/datasets/{geo_id}/magnetic/lineaments")
def extract_magnetic_lineaments(
    geo_id: str,
    body: LineamentExtractBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Extract candidate magnetic lineaments from edge-enhanced TMI products.

    Candidates are NOT confirmed faults. used_in_inference remains false.
    """
    try:
        record, report = _service(service_config).extract_candidate_lineaments(
            geo_id,
            percentile=body.percentile,
            min_length_cells=body.min_length_cells,
            min_component_cells=body.min_component_cells,
            density_window_m=body.density_window_m,
            use_residual_blend=body.use_residual_blend,
            ensure_derivatives=body.ensure_derivatives,
            nodata=body.nodata,
        )
    except ManualTrainingError as exc:
        return _error(exc)
    return {
        "dataset": record.to_dict(),
        "lineaments": report,
        "scientific_validation_status": "NOT_VALIDATED",
        "not_confirmed_faults_or_fractures": True,
        "used_in_inference": False,
    }


@router.get("/datasets/{geo_id}/derived/{filename}")
def get_derived_file(
    geo_id: str,
    filename: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    """Serve a derived magnetic product (GeoTIFF, PNG preview, or JSON)."""
    safe = filename.replace("\\", "/").split("/")[-1]
    if not safe or ".." in safe:
        return _error(
            ManualTrainingError("Invalid derived filename.", code="DERIVED_PATH"),
            status=400,
        )
    base = _storage(service_config).dataset_dir(geo_id) / "working" / "derived"
    path = base / safe
    if not path.is_file():
        # Allow lineament subdirectory artifacts without path traversal.
        nested = base / "lineaments" / safe
        if nested.is_file():
            path = nested
    if not path.is_file():
        return _error(
            ManualTrainingError("Derived file not found.", code="DERIVED_NOT_FOUND"),
            status=404,
        )
    media = "application/octet-stream"
    if safe.endswith(".png"):
        media = "image/png"
    elif safe.endswith(".json") or safe.endswith(".geojson"):
        media = "application/json"
    elif safe.endswith(".tif") or safe.endswith(".tiff"):
        media = "image/tiff"
    return FileResponse(path, media_type=media, filename=safe)


@router.post("/datasets/{geo_id}/compatibility")
def set_compatibility(
    geo_id: str,
    body: CompatibilityBody,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_manage_geological),
) -> Any:
    try:
        record = _service(service_config).set_compatibility_decision(
            geo_id, decision=body.decision, notes=body.notes
        )
    except ManualTrainingError as exc:
        return _error(exc, status=404 if exc.code == "DATASET_NOT_FOUND" else 400)
    return {
        "dataset": record.to_dict(),
        "feature_compatibility": record.feature_compatibility,
    }


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
