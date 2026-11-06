"""Release-shell HTTP API (requires SSRI_RELEASE_SHELL=true)."""

from __future__ import annotations

import hashlib
import json
import shutil
import uuid
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ssri_model.api.dependencies import (
    get_job_executor,
    get_job_service,
    get_service_config,
    require_read_status,
    require_run_inference,
)
from ssri_model.api.job_workers import run_training_job
from ssri_model.auth.models import AuthenticatedPrincipal
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.models import JobStatus, JobType
from ssri_model.jobs.service import JobService
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.ingest import ingest_zip_bytes
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
from ssri_model.release_shell.channel_schema import (
    CHANNEL_NAMES_V1,
    CHANNEL_NAMES_V2,
    SCHEMA_V1,
    SCHEMA_V2,
)
from ssri_model.release_shell.flags import (
    default_limitations,
    preview_unevaluated_scores,
    release_shell_block_size_deg,
    release_shell_block_size_km,
    release_shell_buffer_km,
    release_shell_enabled,
    release_shell_min_blocks,
    release_shell_min_held_out_blocks,
    release_shell_min_tiles,
)
from ssri_model.release_shell.labels_inventory import parse_label_csv, parse_label_geojson
from ssri_model.release_shell.lineaments import LineamentMethod, load_lineament_segments
from ssri_model.release_shell.spatial_split import DEFAULT_BLOCK_SIZE_DEG, resolve_block_size_deg
from ssri_model.release_shell.validator import (
    validate_point_grid_layer,
    validate_release_shell_dataset,
)
from ssri_model.service.config import ServiceConfig

router = APIRouter(prefix="/release-shell", tags=["release-shell"])


def _storage(cfg: ServiceConfig) -> TrainingStorage:
    return TrainingStorage(cfg.output_root)


def _registry(cfg: ServiceConfig) -> ModelRegistry:
    return ModelRegistry(_storage(cfg))


def _require_shell() -> JSONResponse | None:
    if not release_shell_enabled():
        return JSONResponse(
            status_code=403,
            content={
                "error": {
                    "code": "RELEASE_SHELL_DISABLED",
                    "message": "Set SSRI_RELEASE_SHELL=true to use the upload-and-train shell.",
                }
            },
        )
    return None


class StartShellTrainBody(BaseModel):
    dataset_id: str
    epochs: int = Field(default=3, ge=1, le=500)
    batch_size: int = Field(default=2, ge=1, le=64)
    learning_rate: float = Field(default=1e-3, gt=0, le=1.0)
    seeds: list[int] = Field(default_factory=lambda: [42, 43, 44])
    device: str = Field(default="cpu", pattern="^(auto|cpu|cuda)$")
    model_name: str | None = None


def _resolved_block_size_deg() -> float | None:
    """Resolved block size in degrees, or None if the env pair is invalid."""
    try:
        return resolve_block_size_deg(
            block_size_deg=release_shell_block_size_deg(),
            block_size_km=release_shell_block_size_km(),
        )
    except ValueError:
        return None


@router.get("/status")
def shell_status() -> dict[str, Any]:
    return {
        "release_shell_enabled": release_shell_enabled(),
        "limitations": default_limitations(),
        "score_framing": "relative susceptibility rankings",
        "scientific_validation_status": "NOT_VALIDATED",
        "settings": {
            "block_size_deg": _resolved_block_size_deg(),
            "default_block_size_deg": DEFAULT_BLOCK_SIZE_DEG,
            "block_size_km_override": release_shell_block_size_km(),
            "block_size_deg_override": release_shell_block_size_deg(),
            "buffer_km": release_shell_buffer_km(),
            "minimums": {
                "tiles_per_hazard": release_shell_min_tiles(),
                "blocks": release_shell_min_blocks(),
                "held_out_blocks": release_shell_min_held_out_blocks(),
            },
            "preview_unevaluated_scores": preview_unevaluated_scores(),
            "supported_channel_schemas": [SCHEMA_V1, SCHEMA_V2],
            "default_channel_schema": SCHEMA_V1,
            "channel_schemas": {
                SCHEMA_V1: {
                    "channel_count": len(CHANNEL_NAMES_V1),
                    "channel_names": list(CHANNEL_NAMES_V1),
                },
                SCHEMA_V2: {
                    "channel_count": len(CHANNEL_NAMES_V2),
                    "channel_names": list(CHANNEL_NAMES_V2),
                },
            },
        },
    }


@router.post("/datasets/{dataset_id}/upload")
async def shell_upload(
    dataset_id: str,
    file: UploadFile = File(...),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> Any:
    blocked = _require_shell()
    if blocked:
        return blocked
    storage = _storage(service_config)
    raw = await file.read()
    try:
        ingest_zip_bytes(
            storage,
            dataset_id,
            filename=file.filename or "upload.zip",
            content=raw,
        )
    except ManualTrainingError as exc:
        status = 413 if exc.code == "UPLOAD_TOO_LARGE" else 400
        return JSONResponse(
            status_code=status,
            content={"error": {"code": exc.code, "message": exc.message}},
        )
    return {"dataset_id": dataset_id, "uploaded": True, "bytes": len(raw)}


@router.post("/datasets/{dataset_id}/validate")
def shell_validate(
    dataset_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    blocked = _require_shell()
    if blocked:
        return blocked
    storage = _storage(service_config)
    record = storage.get_dataset(dataset_id)
    report = validate_release_shell_dataset(record.root_path)
    out = Path(record.root_path) / "release_shell_validation.json"
    out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if report.get("can_train") and report.get("spatial_split"):
        _apply_spatial_split_to_dataset(Path(record.root_path), report["spatial_split"])
        report = validate_release_shell_dataset(record.root_path)
        out.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"validation": report}


def _apply_spatial_split_to_dataset(root: Path, split: dict[str, Any]) -> None:
    by_id: dict[str, Path] = {}
    for split_name in ("train", "validation", "test"):
        d = root / split_name
        if not d.is_dir():
            continue
        for p in d.iterdir():
            if p.is_dir():
                by_id[p.name] = p

    staging = root / "_split_staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir()

    def place(ids: list[str], dest_split: str) -> None:
        dest = staging / dest_split
        dest.mkdir(parents=True, exist_ok=True)
        for sid in ids:
            src = by_id.get(sid)
            if src is None:
                continue
            target = dest / sid
            if not target.exists():
                shutil.copytree(src, target)

    place(list(split.get("train") or []), "train")
    place(list(split.get("validation") or []), "validation")
    place(list(split.get("test") or []), "test")

    for split_name in ("train", "validation", "test"):
        d = root / split_name
        if d.exists():
            shutil.rmtree(d)
        src = staging / split_name
        if src.exists():
            shutil.move(str(src), str(d))
        else:
            d.mkdir(parents=True, exist_ok=True)
    shutil.rmtree(staging, ignore_errors=True)

    manifest_path = root / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    train_ids = list(split.get("train") or [])
    val_ids = list(split.get("validation") or [])
    test_ids = list(split.get("test") or [])
    manifest["splits"] = {
        "train": train_ids,
        "validation": val_ids,
        "test": test_ids,
    }
    manifest["train_count"] = len(train_ids)
    manifest["validation_count"] = len(val_ids)
    manifest["test_count"] = len(test_ids)
    # Ensure Stage 2.5 DatasetManifest required keys survive rewrite
    manifest.setdefault("dataset_name", manifest.get("name") or root.name)
    manifest.setdefault("version", "0.0.0-release-shell")
    manifest.setdefault("created_at", "1970-01-01T00:00:00+00:00")
    manifest.setdefault("resolution", 30.0)
    manifest.setdefault("crs", "EPSG:4326")
    if "normalization" not in manifest:
        from ssri_model.ml.normalization import NormalizationConfig

        manifest["normalization"] = NormalizationConfig.default().as_dict()
    manifest["spatial_split"] = {
        "policy": split.get("policy"),
        "buffer_km": split.get("buffer_km"),
        "train_blocks": split.get("train_blocks"),
        "validation_blocks": split.get("validation_blocks"),
        "test_blocks": split.get("test_blocks"),
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    (root / "split_manifest.json").write_text(json.dumps(split, indent=2), encoding="utf-8")


@router.post("/jobs", status_code=202)
def shell_start_training(
    body: StartShellTrainBody,
    service_config: ServiceConfig = Depends(get_service_config),
    job_service: JobService = Depends(get_job_service),
    job_executor: JobExecutor = Depends(get_job_executor),
    principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> Any:
    blocked = _require_shell()
    if blocked:
        return blocked
    storage = _storage(service_config)
    record = storage.get_dataset(body.dataset_id)
    report = validate_release_shell_dataset(record.root_path)
    if not report.get("can_train"):
        fails = [c for c in report.get("checks", []) if c.get("status") == "FAIL"]
        reason = fails[0]["message"] if fails else "Validation failed."
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "VALIDATION_FAILED",
                    "message": f"Training refused: {reason}",
                    "validation": report,
                }
            },
        )

    root = Path(record.root_path)
    data_hash = hashlib.sha256((root / "manifest.json").read_bytes()).hexdigest().upper()
    run_id = f"run_{uuid.uuid4().hex[:12]}"
    seed = body.seeds[0] if body.seeds else 42
    meta = {
        "release_shell": True,
        "seeds": body.seeds,
        "data_hash": data_hash,
        "split_manifest": json.loads((root / "split_manifest.json").read_text(encoding="utf-8"))
        if (root / "split_manifest.json").exists()
        else None,
        "config": body.model_dump(),
    }
    (storage.run_dir(run_id) / "release_shell_train_meta.json").write_text(
        json.dumps(meta, indent=2), encoding="utf-8"
    )

    payload = {
        "run_id": run_id,
        "dataset_id": body.dataset_id,
        "epochs": body.epochs,
        "batch_size": body.batch_size,
        "learning_rate": body.learning_rate,
        "seed": seed,
        "model_name": body.model_name,
        "device": body.device,
        "output_root": service_config.output_root,
        "release_shell_eval": True,
        "release_shell_seeds": body.seeds,
    }
    job_record = job_service.create_job(
        request_id=f"shell-train-{run_id}",
        job_type=JobType.TRAINING,
        principal=principal,
        scientific_validation_status="NOT_VALIDATED",
        payload=payload,
    )
    storage.write_progress(
        run_id,
        {
            "phase": "queued",
            "message": "Release-shell training job queued.",
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
    return {
        "job_id": job_record.job_id,
        "run_id": run_id,
        "message": (
            "Training started. Poll /api/v1/jobs/{job_id}. "
            "Held-out evaluation runs automatically after training."
        ),
        "data_hash": data_hash,
        "scientific_validation_status": "NOT_VALIDATED",
        "limitations": default_limitations(),
    }


@router.get("/models/{model_id}/evaluation")
def shell_get_evaluation(
    model_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> Any:
    blocked = _require_shell()
    if blocked:
        return blocked
    registry = _registry(service_config)
    try:
        rec = registry.get_model(model_id)
    except Exception as exc:  # noqa: BLE001
        return JSONResponse(
            status_code=404,
            content={"error": {"message": str(exc)}},
        )
    candidates = [
        Path(rec.checkpoint_path).resolve().parent / "release_shell_evaluation.json",
        Path(rec.checkpoint_path).resolve().parent.parent / "release_shell_evaluation.json",
    ]
    for path in candidates:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    return JSONResponse(
        status_code=404,
        content={"error": {"message": "No evaluation report found for this model yet."}},
    )


@router.post("/layers/validate")
async def shell_validate_layer(
    file: UploadFile = File(...),
    layer_name: str = Form(...),
    crs: str = Form(""),
    working_crs: str | None = Form(None),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> Any:
    """Validate one declared feature layer (point-grid CSV). CRS is required.

    A single layer is FEATURE_LAYER_ONLY — this never trains. Surfaces
    unit-sanity warnings (for example negative overburden_thickness) explicitly.
    """
    blocked = _require_shell()
    if blocked:
        return blocked
    raw = await file.read()
    report = validate_point_grid_layer(
        raw,
        filename=file.filename or "layer.csv",
        layer_name=layer_name,
        crs=crs,
        working_crs=(working_crs or None),
    )
    status = 200 if report.get("overall") != "FAIL" else 400
    return JSONResponse(status_code=status, content={"layer": report})


@router.post("/labels/inventory")
async def shell_label_inventory(
    file: UploadFile = File(...),
    crs: str = Form(""),
    date_column: str | None = Form(None),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> Any:
    """Summarise a label inventory (CSV or GeoJSON). CRS is required."""
    blocked = _require_shell()
    if blocked:
        return blocked
    raw = await file.read()
    filename = file.filename or "labels.csv"
    try:
        if filename.lower().endswith((".geojson", ".json")):
            inventory = parse_label_geojson(raw, crs=crs, filename=filename)
        else:
            inventory = parse_label_csv(
                raw, crs=crs, filename=filename, date_column=date_column or "date"
            )
    except (ManualTrainingError, ValueError, KeyError) as exc:
        code = getattr(exc, "code", "LABEL_PARSE")
        message = getattr(exc, "message", str(exc))
        return JSONResponse(
            status_code=400, content={"error": {"code": code, "message": message}}
        )
    return {"labels": inventory.to_dict()}


@router.post("/lineaments/inspect")
async def shell_lineaments_inspect(
    file: UploadFile = File(...),
    _principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> Any:
    """Inspect a lineament vector file (GeoJSON). Reports segment count and bbox."""
    blocked = _require_shell()
    if blocked:
        return blocked
    raw = await file.read()
    try:
        segments = load_lineament_segments(raw)
    except (ValueError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return JSONResponse(
            status_code=400,
            content={
                "error": {
                    "code": "LINEAMENT_PARSE",
                    "message": f"Could not read lineament GeoJSON: {exc}",
                }
            },
        )
    xs = [v for seg in segments for v in (seg[0], seg[2])]
    ys = [v for seg in segments for v in (seg[1], seg[3])]
    bbox = (
        {"x_min": min(xs), "x_max": max(xs), "y_min": min(ys), "y_max": max(ys)}
        if segments
        else None
    )
    return {
        "lineaments": {
            "n_segments": len(segments),
            "bbox": bbox,
            "method": LineamentMethod().to_dict(),
            "note": (
                "Coordinates are in the layer's declared projected CRS (metres assumed). "
                "Derive lineament_density / lineament_distance per grid cell before training."
            ),
        }
    }
