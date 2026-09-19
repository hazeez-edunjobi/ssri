"""Product assessment API routes."""

from __future__ import annotations

import os
import secrets
from pathlib import Path
from typing import Any

import numpy as np
import torch
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field

from ssri_model.api.acquisition import acquire_feature_array_for_bbox, live_acquisition_enabled
from ssri_model.api.checkpoint_identity import (
    dataset_manifest_fields,
    enforce_fixture_checkpoint_policy,
    sha256_file,
)
from ssri_model.api.config import APIConfig
from ssri_model.api.demo_assessment import build_demo_assessment_response
from ssri_model.api.dependencies import (
    get_api_config,
    get_service_config,
    require_run_inference_rate_limited,
)
from ssri_model.api.domain_similarity import resolve_domain_similarity
from ssri_model.api.geojson import point_bbox, validate_polygon_geojson
from ssri_model.api.geotiff_output import write_probability_geotiff
from ssri_model.auth.models import AuthenticatedPrincipal
from ssri_model.inference.checkpoint import load_inference_checkpoint
from ssri_model.ml.constants import CHANNEL_COUNT, SUPPORTED_LABELS
from ssri_model.service.config import ServiceConfig
from ssri_model.service.exceptions import InvalidServiceRequestError
from ssri_model.service.validation import reject_path_traversal, sanitize_request_id
from ssri_model.storage import build_object_storage_from_env
from ssri_model.uncertainty import (
    UncertaintyConfig,
    assess_from_mc_samples,
    build_template_explanation,
    embedding_from_features,
    gradient_feature_attribution,
    run_mc_dropout,
)

router = APIRouter(prefix="/assess", tags=["assess"])


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AssessRequestBody(BaseModel):
    """Assessment request.

    Preferred offline path: ``features`` (.npy) + ``checkpoint``.
    Live path: ``point`` or ``polygon_geojson`` + ``checkpoint`` when
    ``SSRI_LIVE_ACQUISITION_ENABLED=true``.
    When ``APIConfig.demo_mode`` is enabled (``SSRI_DEMO_MODE``), live
    acquisition and checkpoint loading are bypassed server-side only.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: f"assess-{secrets.token_hex(6)}")
    checkpoint: str | None = None
    features: str | None = None
    point: GeoPoint | None = None
    polygon_geojson: dict[str, Any] | None = None
    hazards: list[str] = Field(default_factory=lambda: list(SUPPORTED_LABELS))
    mc_samples: int = Field(default=20, ge=2, le=200)
    model_version: str = "ssri-model"
    produce_geotiff: bool = False
    resolution_m: float = Field(default=30.0, gt=1.0, le=500.0)


class AssessResponseBody(BaseModel):
    assessment_id: str
    hazard_profiles: list[dict[str, Any]]
    explanation: str
    model_version: str
    spatial_output_url: str | None = None
    notes: list[str] = Field(default_factory=list)
    request_id: str
    checkpoint_sha256: str
    checkpoint_dataset_name: str | None = None
    checkpoint_dataset_version: str | None = None
    is_fixture_checkpoint: bool = False
    domain_similarity_calibrated: bool = False


def _load_feature_tensor(path: str) -> torch.Tensor:
    reject_path_traversal(path, field_name="features")
    array = torch.as_tensor(np.load(path))
    if array.ndim == 3:
        array = array.unsqueeze(0)
    if array.ndim != 4 or array.shape[1] != CHANNEL_COUNT:
        raise InvalidServiceRequestError(
            f"features must be shaped (C,H,W) or (B,C,H,W) with C={CHANNEL_COUNT}"
        )
    return array.float()


def _array_to_tensor(array: np.ndarray) -> torch.Tensor:
    tensor = torch.as_tensor(array).float()
    if tensor.ndim == 3:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 4 or tensor.shape[1] != CHANNEL_COUNT:
        raise InvalidServiceRequestError(
            f"acquired features must have {CHANNEL_COUNT} channels"
        )
    return tensor


def _resolve_features(
    body: AssessRequestBody,
    *,
    output_root: Path,
    assessment_id: str,
) -> tuple[torch.Tensor, list[str]]:
    notes: list[str] = []
    if body.features is not None:
        return _load_feature_tensor(body.features), notes

    if body.point is None and body.polygon_geojson is None:
        raise InvalidServiceRequestError(
            "Assessment requires 'features' or a live AOI ('point'/'polygon_geojson')."
        )
    if body.checkpoint is None:
        raise InvalidServiceRequestError(
            "Live AOI assessment requires a 'checkpoint' path."
        )
    if not live_acquisition_enabled():
        raise InvalidServiceRequestError(
            "Live AOI feature acquisition is not enabled in this deployment. "
            "Provide offline 'features' (.npy) and 'checkpoint', or set "
            "SSRI_LIVE_ACQUISITION_ENABLED=true with GEE/OpenTopography configured."
        )

    if body.polygon_geojson is not None:
        bbox = validate_polygon_geojson(body.polygon_geojson)
        notes.append("aoi_source=polygon_geojson")
    else:
        assert body.point is not None
        bbox = point_bbox(body.point.longitude, body.point.latitude)
        notes.append("aoi_source=point")

    acq_dir = output_root / "assessments" / assessment_id / "acquisition"
    array, meta = acquire_feature_array_for_bbox(
        bbox,
        output_dir=acq_dir,
        resolution_m=body.resolution_m,
    )
    notes.append(f"acquisition_bbox={meta['bbox']}")
    return _array_to_tensor(array), notes


def _persist_assessment_response(
    *,
    output_root: Path,
    assessment_id: str,
    body: AssessResponseBody,
) -> Path:
    assess_dir = output_root / "assessments" / assessment_id
    assess_dir.mkdir(parents=True, exist_ok=True)
    path = assess_dir / "assess_response.json"
    path.write_text(body.model_dump_json(indent=2), encoding="utf-8")
    return path


@router.post("", response_model=AssessResponseBody, status_code=200)
def assess_endpoint(
    body: AssessRequestBody,
    api_config: APIConfig = Depends(get_api_config),
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_run_inference_rate_limited),
) -> AssessResponseBody:
    request_id = sanitize_request_id(body.request_id)
    output_root = Path(service_config.output_root)

    # Presentation path — controlled only by server ``SSRI_DEMO_MODE``.
    if api_config.demo_mode:
        if body.point is None and body.polygon_geojson is None and body.features is None:
            raise InvalidServiceRequestError(
                "Assessment requires 'features' or a live AOI ('point'/'polygon_geojson')."
            )
        payload = build_demo_assessment_response(
            request_id=request_id,
            hazards=body.hazards,
            model_version=body.model_version,
            point=(
                {"latitude": body.point.latitude, "longitude": body.point.longitude}
                if body.point is not None
                else None
            ),
            polygon_geojson=body.polygon_geojson,
            checkpoint=body.checkpoint,
        )
        payload["notes"] = list(payload.get("notes") or []) + [
            f"requested_by={principal.key_id}",
        ]
        response = AssessResponseBody.model_validate(payload)
        _persist_assessment_response(
            output_root=output_root,
            assessment_id=response.assessment_id,
            body=response,
        )
        return response

    assessment_id = f"assess-{secrets.token_hex(8)}"

    if body.checkpoint is None:
        raise InvalidServiceRequestError("Assessment requires 'checkpoint'.")

    features, acquisition_notes = _resolve_features(
        body,
        output_root=output_root,
        assessment_id=assessment_id,
    )
    reject_path_traversal(body.checkpoint, field_name="checkpoint")
    checkpoint_path = Path(body.checkpoint)
    if not checkpoint_path.is_file():
        raise InvalidServiceRequestError(f"Checkpoint not found: {body.checkpoint}")

    checkpoint_sha256 = sha256_file(checkpoint_path)
    model, payload = load_inference_checkpoint(
        body.checkpoint,
        device=torch.device("cpu"),
    )
    dataset_name, dataset_version = dataset_manifest_fields(payload)
    is_fixture = enforce_fixture_checkpoint_policy(dataset_name)

    cfg = UncertaintyConfig(mc_samples=body.mc_samples, seed=42)
    samples = run_mc_dropout(model, features, config=cfg)
    embedding = embedding_from_features(features)
    domain = resolve_domain_similarity(embedding)

    drivers: dict[int, list[str]] = {}
    for index, hazard in enumerate(SUPPORTED_LABELS):
        if hazard not in body.hazards:
            continue
        ranked = gradient_feature_attribution(model, features, class_index=index)
        drivers[index] = [name for name, _ in ranked[:5]]

    selected = [name for name in SUPPORTED_LABELS if name in body.hazards]
    selected_indices = [SUPPORTED_LABELS.index(name) for name in selected]
    selected_samples = samples[:, selected_indices]

    result = assess_from_mc_samples(
        selected_samples,
        hazard_names=selected,
        domain_similarity=domain.score,
        domain_similarity_calibrated=domain.calibrated,
        config=cfg,
        primary_drivers_by_class={
            i: drivers.get(SUPPORTED_LABELS.index(name), [])
            for i, name in enumerate(selected)
        },
        assessment_id=assessment_id,
        model_version=body.model_version,
    )
    explanation = build_template_explanation(result.hazard_profiles)

    spatial_url: str | None = None
    if body.produce_geotiff and selected_indices:
        with torch.no_grad():
            model.eval()
            logits = model(features)
            probs = torch.sigmoid(logits)[0, selected_indices[0]].detach().cpu().numpy()
        tif_path = (
            output_root
            / "assessments"
            / assessment_id
            / f"{selected[0]}_probability.tif"
        )
        write_probability_geotiff(tif_path, probs)
        storage = build_object_storage_from_env()
        key = storage.put_bytes(
            f"assessments/{assessment_id}/{selected[0]}_probability.tif",
            tif_path.read_bytes(),
            content_type="image/tiff",
        )
        expires = int(os.getenv("SSRI_OBJECT_STORAGE_URL_EXPIRES", "3600"))
        spatial_url = storage.signed_url(key, expires_seconds=expires)

    response = AssessResponseBody(
        assessment_id=result.assessment_id,
        hazard_profiles=[profile.to_dict() for profile in result.hazard_profiles],
        explanation=explanation,
        model_version=result.model_version,
        spatial_output_url=spatial_url,
        notes=list(result.notes)
        + acquisition_notes
        + list(domain.notes)
        + [
            f"requested_by={principal.key_id}",
            f"request_id={request_id}",
            f"checkpoint_sha256={checkpoint_sha256}",
            f"is_fixture_checkpoint={str(is_fixture).lower()}",
        ],
        request_id=request_id,
        checkpoint_sha256=checkpoint_sha256,
        checkpoint_dataset_name=dataset_name,
        checkpoint_dataset_version=dataset_version,
        is_fixture_checkpoint=is_fixture,
        domain_similarity_calibrated=domain.calibrated,
    )
    _persist_assessment_response(
        output_root=output_root,
        assessment_id=assessment_id,
        body=response,
    )
    return response
