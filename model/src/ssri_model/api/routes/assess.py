"""Product assessment API routes."""

from __future__ import annotations

import json
import os
import secrets
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import torch
from fastapi import APIRouter, Depends
from fastapi.responses import FileResponse, Response
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
    require_run_assess_rate_limited,
)
from ssri_model.api.domain_similarity import resolve_domain_similarity
from ssri_model.api.geojson import point_bbox, validate_polygon_geojson
from ssri_model.api.geotiff_output import write_probability_geotiff
from ssri_model.api.assess_conditioning import sample_conditioning_features
from ssri_model.api.geological_conditioning_overlay import (
    enrich_conditioning_with_geological_catalogue,
)
from ssri_model.api.location_provenance import build_location_provenance
from ssri_model.auth.authorization import has_permission
from ssri_model.auth.exceptions import AuthorizationError
from ssri_model.auth.models import AuthenticatedPrincipal, Permission
from ssri_model.inference.checkpoint import load_inference_checkpoint
from ssri_model.manual_training.exceptions import ModelNotFoundError, UnsafePathError
from ssri_model.manual_training.registry import ModelRegistry
from ssri_model.manual_training.storage import TrainingStorage
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

_NO_PRODUCTION_CHECKPOINT_MESSAGE = (
    "No valid production checkpoint is configured. Promote a trained "
    "Stage 2.5 (13-channel) model in the training registry, then retry the "
    "assessment. Clients should not supply server filesystem paths."
)

_CHECKPOINT_OVERRIDE_DENIED = (
    "Explicit checkpoint paths require operator authorization. "
    "Ordinary assessments use the promoted production model."
)

_MODEL_ID_OVERRIDE_DENIED = (
    "Selecting a non-promoted model requires operator authorization. "
    "Ordinary assessments use the promoted production model."
)

router = APIRouter(prefix="/assess", tags=["assess"])


def can_override_assessment_checkpoint(principal: AuthenticatedPrincipal) -> bool:
    """Operators/admins (RUN_INFERENCE) may select paths or non-active model ids."""
    return has_permission(principal, Permission.RUN_INFERENCE)


class GeoPoint(BaseModel):
    model_config = ConfigDict(extra="forbid")
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)


class AssessRequestBody(BaseModel):
    """Assessment request.

    Ordinary clients omit ``checkpoint``. The server resolves the promoted Stage
    2.5 model from the training registry (``active.json``). Customers must not
    supply server filesystem paths.

    Preferred offline path: ``features`` (.npy); checkpoint resolved from the
    active registry (or optional operator ``checkpoint`` / ``model_id``).
    Live path: ``point`` or ``polygon_geojson`` when
    ``SSRI_LIVE_ACQUISITION_ENABLED=true``, with the same server-side checkpoint
    resolution.

    When ``APIConfig.demo_mode`` is enabled (``SSRI_DEMO_MODE``), live
    acquisition and checkpoint loading are bypassed server-side only.
    """

    model_config = ConfigDict(extra="forbid")

    request_id: str = Field(default_factory=lambda: f"assess-{secrets.token_hex(6)}")
    checkpoint: str | None = Field(
        default=None,
        description=(
            "Optional operator filesystem override under the service output root. "
            "Requires RUN_INFERENCE. Ordinary assessments omit this field; the "
            "server injects the promoted registry checkpoint internally."
        ),
    )
    model_id: str | None = Field(
        default=None,
        description=(
            "Optional registered training-model id. When set to the promoted "
            "model (or by an operator for a non-active model), the server "
            "resolves the checkpoint without exposing filesystem paths to clients."
        ),
    )
    features: str | None = None
    point: GeoPoint | None = None
    polygon_geojson: dict[str, Any] | None = None
    hazards: list[str] = Field(default_factory=lambda: list(SUPPORTED_LABELS))
    mc_samples: int = Field(default=20, ge=2, le=200)
    model_version: str = "ssri-model"
    produce_geotiff: bool = False
    resolution_m: float = Field(default=30.0, gt=1.0, le=500.0)
    # Honoured only when SSRI_DEMO_MODE is on; ignored for live inference.
    demo_scenario_key: str | None = Field(
        default=None,
        description=(
            "Optional presentation catalogue scenario key. Used only when "
            "SSRI_DEMO_MODE is enabled; ignored otherwise."
        ),
    )


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
    channel_schema_version: str | None = None
    channel_names: list[str] | None = None
    checkpoint_id: str | None = None
    evaluation_summary: dict[str, Any] | None = None
    location_provenance: dict[str, Any] | None = None
    conditioning_features: dict[str, Any] | None = None
    spatial_output_expires_seconds: int | None = None
    spatial_output_hazard: str | None = None
    spatial_output_crs: str | None = None
    spatial_output_georef_quality: str | None = None
    spatial_object_key: str | None = None


_ALLOWED_FEATURE_CHANNEL_COUNTS = frozenset({CHANNEL_COUNT, 16})


def _model_registry(output_root: Path) -> ModelRegistry:
    return ModelRegistry(TrainingStorage(str(output_root)))


def _ensure_path_under_root(path: Path, *, root: Path, label: str) -> Path:
    """Resolve ``path`` and require it stays under ``root`` (blocks symlink escape)."""
    resolved = path.resolve()
    root_resolved = root.resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise InvalidServiceRequestError(
            f"{label} resolves outside the allowed storage root."
        ) from exc
    return resolved


def resolve_assessment_checkpoint(
    *,
    checkpoint: str | None,
    model_id: str | None,
    output_root: Path,
    principal: AuthenticatedPrincipal,
) -> tuple[str, str]:
    """Resolve a filesystem checkpoint from client path, model id, or active registry.

    Ordinary ``RUN_ASSESS`` principals may only use the promoted active model.
    Explicit filesystem paths and non-active ``model_id`` selection require
    ``RUN_INFERENCE`` (operator/admin).

    Returns ``(checkpoint_path, source)`` where ``source`` is one of
    ``client_path``, ``model_id``, or ``active_registry``.
    """
    allow_override = can_override_assessment_checkpoint(principal)
    registry = _model_registry(output_root)
    models_root = registry.storage.models_dir
    output_root_path = Path(output_root)

    if checkpoint:
        if not allow_override:
            raise AuthorizationError(_CHECKPOINT_OVERRIDE_DENIED)
        reject_path_traversal(checkpoint, field_name="checkpoint")
        candidate = Path(checkpoint)
        # Operator/lab overrides must stay under the service output root.
        resolved = _ensure_path_under_root(
            candidate,
            root=output_root_path,
            label="Checkpoint path",
        )
        if not resolved.is_file():
            raise InvalidServiceRequestError(
                "Checkpoint not found at the provided operator path."
            )
        return str(resolved), "client_path"

    active_id = registry.get_active_model_id()

    if model_id:
        if model_id == active_id:
            # Explicitly naming the promoted model is equivalent to active resolution.
            pass
        elif not allow_override:
            raise AuthorizationError(_MODEL_ID_OVERRIDE_DENIED)
        else:
            try:
                record = registry.get_model(model_id)
            except ModelNotFoundError as exc:
                raise InvalidServiceRequestError(
                    "The requested registered model was not found in the training registry."
                ) from exc
            path = _ensure_path_under_root(
                Path(record.checkpoint_path),
                root=models_root,
                label="Registered model checkpoint",
            )
            if not path.is_file():
                raise InvalidServiceRequestError(
                    "The requested registered model exists but its checkpoint file is "
                    "unavailable. Re-register or re-train the model, then promote it."
                )
            return str(path), "model_id"

    try:
        active = registry.get_active_checkpoint()
    except (ModelNotFoundError, UnsafePathError, OSError, ValueError, TypeError):
        active = None
    if active:
        path = _ensure_path_under_root(
            Path(active),
            root=models_root,
            label="Promoted model checkpoint",
        )
        if path.is_file():
            return str(path), "active_registry"
        # Durable recovery: active.json / registry may carry object_storage_key.
        try:
            active_id = registry.get_active_model_id()
            record = registry.get_model(active_id) if active_id else None
            object_key = getattr(record, "object_storage_key", None) if record else None
            if object_key:
                from ssri_model.storage.durable import resolve_checkpoint_path

                recovered = resolve_checkpoint_path(
                    local_path=path,
                    object_key=object_key,
                    cache_dir=models_root / (active_id or "active") / ".object_cache",
                )
                if recovered.is_file():
                    return str(recovered), "active_registry_object_storage"
        except Exception:
            pass
        raise InvalidServiceRequestError(
            "A promoted model is selected, but its checkpoint file is unavailable. "
            "Re-promote a valid Stage 2.5 checkpoint, then retry."
        )

    raise InvalidServiceRequestError(_NO_PRODUCTION_CHECKPOINT_MESSAGE)


def _load_feature_tensor(path: str) -> torch.Tensor:
    reject_path_traversal(path, field_name="features")
    array = torch.as_tensor(np.load(path))
    if array.ndim == 3:
        array = array.unsqueeze(0)
    if array.ndim != 4 or array.shape[1] not in _ALLOWED_FEATURE_CHANNEL_COUNTS:
        raise InvalidServiceRequestError(
            "features must be shaped (C,H,W) or (B,C,H,W) with "
            f"C={CHANNEL_COUNT} (v1) or C=16 (v2)"
        )
    return array.float()


def _array_to_tensor(array: np.ndarray) -> torch.Tensor:
    tensor = torch.as_tensor(array).float()
    if tensor.ndim == 3:
        tensor = tensor.unsqueeze(0)
    if tensor.ndim != 4 or tensor.shape[1] not in _ALLOWED_FEATURE_CHANNEL_COUNTS:
        raise InvalidServiceRequestError(
            f"acquired features must have {CHANNEL_COUNT} (v1) or 16 (v2) channels"
        )
    return tensor


def _resolve_features(
    body: AssessRequestBody,
    *,
    output_root: Path,
    assessment_id: str,
    checkpoint_resolved: bool,
) -> tuple[torch.Tensor, list[str], dict[str, Any] | None]:
    notes: list[str] = []
    if body.features is not None:
        return _load_feature_tensor(body.features), notes, None

    if body.point is None and body.polygon_geojson is None:
        raise InvalidServiceRequestError(
            "Assessment requires 'features' or a live AOI ('point'/'polygon_geojson')."
        )
    if not checkpoint_resolved:
        raise InvalidServiceRequestError(_NO_PRODUCTION_CHECKPOINT_MESSAGE)
    if not live_acquisition_enabled():
        raise InvalidServiceRequestError(
            "Live AOI feature acquisition is not enabled in this deployment. "
            "Provide offline 'features' (.npy), or set "
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
    return _array_to_tensor(array), notes, meta


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
    try:
        from ssri_model.storage.durable import mirror_assessment_payload

        mirror_assessment_payload(assess_dir, assessment_id)
    except Exception:
        pass
    return path


@router.post("", response_model=AssessResponseBody, status_code=200)
def assess_endpoint(
    body: AssessRequestBody,
    api_config: APIConfig = Depends(get_api_config),
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_run_assess_rate_limited),
) -> AssessResponseBody:
    request_id = sanitize_request_id(body.request_id)
    output_root = Path(service_config.output_root)

    # Presentation path — development-only; forced off in production/staging
    # (see APIConfig.resolve_demo_mode). Never invent scores when demo is off.
    if api_config.demo_mode:
        if (
            body.point is None
            and body.polygon_geojson is None
            and body.features is None
            and not body.demo_scenario_key
        ):
            raise InvalidServiceRequestError(
                "Assessment requires 'features', a live AOI ('point'/'polygon_geojson'), "
                "or a presentation demo_scenario_key."
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
            scenario_key=body.demo_scenario_key,
        )
        payload["notes"] = list(payload.get("notes") or []) + [
            f"requested_by={principal.key_id}",
        ]
        if body.point is not None and not payload.get("location_provenance"):
            payload["location_provenance"] = build_location_provenance(
                latitude=body.point.latitude,
                longitude=body.point.longitude,
                resolution_m=body.resolution_m,
                aoi_source="point",
            )
        response = AssessResponseBody.model_validate(payload)
        # Do not persist illustrative demo payloads as production assessments.
        return response

    assessment_id = f"assess-{secrets.token_hex(8)}"

    from ssri_model.release_shell.flags import (
        default_limitations,
        release_shell_enabled,
    )

    try:
        resolved_checkpoint, checkpoint_source = resolve_assessment_checkpoint(
            checkpoint=body.checkpoint,
            model_id=body.model_id,
            output_root=output_root,
            principal=principal,
        )
    except AuthorizationError:
        raise
    except InvalidServiceRequestError:
        if (
            body.checkpoint is None
            and body.model_id is None
            and release_shell_enabled()
        ):
            from fastapi.responses import JSONResponse

            return JSONResponse(  # type: ignore[return-value]
                status_code=200,
                content={
                    "status": "no_trained_model",
                    "message": (
                        "No trained model checkpoint is configured. "
                        "Upload a labelled dataset, train, then promote a checkpoint "
                        "before running assess."
                    ),
                    "scientific_validation_status": "NOT_VALIDATED",
                    "score_framing": "relative susceptibility rankings",
                    "limitations": default_limitations(),
                    "request_id": request_id,
                    "assessment_id": assessment_id,
                },
            )
        raise

    features, acquisition_notes, acquisition_meta = _resolve_features(
        body,
        output_root=output_root,
        assessment_id=assessment_id,
        checkpoint_resolved=True,
    )
    checkpoint_path = Path(resolved_checkpoint)
    if not checkpoint_path.is_file():
        raise InvalidServiceRequestError(
            "Resolved registry checkpoint is unavailable. Promote a valid "
            "Stage 2.5 checkpoint, then retry."
        )

    checkpoint_sha256 = sha256_file(checkpoint_path)
    model, payload = load_inference_checkpoint(
        resolved_checkpoint,
        device=torch.device("cpu"),
    )
    dataset_name, dataset_version = dataset_manifest_fields(payload)
    is_fixture = enforce_fixture_checkpoint_policy(dataset_name)

    model_config = payload.get("model_config") or {}
    expected_channels = int(model_config.get("in_channels") or CHANNEL_COUNT)
    feature_channels = int(features.shape[1])
    if feature_channels != expected_channels:
        raise InvalidServiceRequestError(
            f"Input features have {feature_channels} channels but the checkpoint "
            f"expects {expected_channels}. Live production assessment uses the "
            f"Stage 2.5 {CHANNEL_COUNT}-channel contract; a schema-v2 (16-channel) "
            "stack is not compatible with this checkpoint."
        )

    from ssri_model.release_shell.flags import default_limitations, release_shell_enabled
    from ssri_model.release_shell.meta import load_shell_meta

    shell_meta = load_shell_meta(checkpoint_path) if release_shell_enabled() else None
    query_lat = body.point.latitude if body.point is not None else None
    query_lon = body.point.longitude if body.point is not None else None

    if release_shell_enabled() and shell_meta:
        from ssri_model.release_shell.channel_schema import (
            assert_channels_match,
            schema_from_checkpoint_payload,
        )

        try:
            expected = schema_from_checkpoint_payload(
                {"release_shell": shell_meta, "model_config": payload.get("model_config") or {}}
            )
            # Feature tensor channel count must match checkpoint schema.
            n_feat = int(features.shape[1]) if features.ndim == 4 else int(features.shape[0])
            if n_feat != expected.channel_count:
                missing = list(expected.channel_names[n_feat:]) if n_feat < expected.channel_count else []
                raise InvalidServiceRequestError(
                    "Input features do not match the checkpoint channel schema "
                    f"(version {expected.version}, {expected.channel_count} channels). "
                    + (
                        "Missing channels: " + ", ".join(missing) + "."
                        if missing
                        else f"Received {n_feat} channels."
                    )
                )
            # If payload advertises names, enforce order too.
            advertised = payload.get("channel_names") or (payload.get("model_config") or {}).get(
                "channel_names"
            )
            if advertised:
                assert_channels_match(expected.channel_names, advertised, context="assess features")
        except ValueError as exc:
            raise InvalidServiceRequestError(str(exc)) from exc

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

    if release_shell_enabled():
        from ssri_model.release_shell.assess_contract import build_shell_hazard_profiles

        raw_scores: dict[str, float] = {}
        for profile in result.hazard_profiles:
            pdata = profile.to_dict()
            name = str(pdata.get("hazard_type") or "")
            score = pdata.get("susceptibility_score")
            if score is None:
                score = pdata.get("point_estimate")
            if name and score is not None:
                raw_scores[name] = float(score)
        shell_profiles = build_shell_hazard_profiles(
            shell_meta=shell_meta,
            raw_scores=raw_scores,
            query_lat=query_lat,
            query_lon=query_lon,
            requested=selected,
        )
        # Replace scored profiles with contract-compliant entries (no score if not evaluated).
        # Preserve attribution drivers computed above when the shell entry omitted them.
        for profile in shell_profiles:
            hazard_name = str(profile.get("hazard_type") or "")
            if hazard_name and not profile.get("primary_drivers"):
                try:
                    class_index = SUPPORTED_LABELS.index(hazard_name)
                except ValueError:
                    continue
                if drivers.get(class_index):
                    profile["primary_drivers"] = list(drivers[class_index])
        explanation = (
            "Relative susceptibility rankings only where gate_status is evaluated. "
            "Status remains NOT_VALIDATED. Not for insurance, engineering, safety, "
            "or emergency decisions."
        )
        result_profiles = shell_profiles
    else:
        explanation = build_template_explanation(result.hazard_profiles)
        result_profiles = [profile.to_dict() for profile in result.hazard_profiles]
    spatial_url: str | None = None
    spatial_expires: int | None = None
    spatial_hazard: str | None = None
    spatial_crs: str | None = None
    spatial_georef_quality: str | None = None
    spatial_object_key: str | None = None
    if body.produce_geotiff and selected_indices:
        with torch.no_grad():
            model.eval()
            logits = model(features)
            from ssri_model.release_shell.flags import use_assess_softmax
            from ssri_model.release_shell.probability import (
                logits_to_class_probabilities,
                logits_to_legacy_sigmoid,
            )

            probs_full = (
                logits_to_class_probabilities(logits)
                if use_assess_softmax()
                else logits_to_legacy_sigmoid(logits)
            )
            probs = probs_full[0, selected_indices[0]].detach().cpu().numpy()
        from ssri_model.release_shell.flags import use_assess_softmax as _uas

        score_name = "ranking_score" if _uas() else "probability"
        spatial_hazard = selected[0]
        tif_path = (
            output_root
            / "assessments"
            / assessment_id
            / f"{spatial_hazard}_{score_name}.tif"
        )
        geotiff_transform = None
        geotiff_crs = "EPSG:4326"
        spatial_georef_quality = "placeholder_origin"
        if acquisition_meta and acquisition_meta.get("transform") is not None:
            geotiff_transform = tuple(acquisition_meta["transform"])
            geotiff_crs = str(acquisition_meta.get("crs") or geotiff_crs)
            spatial_georef_quality = "acquisition_grid"
        write_probability_geotiff(
            tif_path,
            probs,
            transform=geotiff_transform,
            crs=geotiff_crs,
        )
        storage = build_object_storage_from_env()
        spatial_object_key = f"assessments/{assessment_id}/{spatial_hazard}_{score_name}.tif"
        key = storage.put_bytes(
            spatial_object_key,
            tif_path.read_bytes(),
            content_type="image/tiff",
        )
        spatial_expires = int(os.getenv("SSRI_OBJECT_STORAGE_URL_EXPIRES", "3600"))
        spatial_url = storage.signed_url(key, expires_seconds=spatial_expires)
        spatial_crs = geotiff_crs

    notes = list(result.notes) + acquisition_notes + list(domain.notes) + [
        f"requested_by={principal.key_id}",
        f"request_id={request_id}",
        f"checkpoint_sha256={checkpoint_sha256}",
        f"checkpoint_source={checkpoint_source}",
        f"is_fixture_checkpoint={str(is_fixture).lower()}",
    ]

    if release_shell_enabled():
        notes.extend(
            [
                "score_framing=relative_susceptibility_rankings",
                "scientific_validation_status=NOT_VALIDATED",
                *[f"limitation={item}" for item in default_limitations()],
            ]
        )
        if shell_meta and shell_meta.get("data_hash"):
            notes.append(f"data_hash={shell_meta['data_hash']}")
        if shell_meta and shell_meta.get("training_region"):
            notes.append(
                "split_policy=whole_5deg_blocks_with_buffer"
            )
    schema_version: str | None = None
    schema_names: list[str] | None = None
    evaluation_summary: dict[str, Any] | None = None
    if release_shell_enabled() and shell_meta:
        schema_version = str(shell_meta.get("channel_schema_version") or "") or None
        names = shell_meta.get("channel_names")
        if isinstance(names, list):
            schema_names = [str(n) for n in names]
        notes.append(f"channel_schema_version={schema_version or 'unknown'}")
        if shell_meta.get("crs"):
            notes.append(f"assess_crs={shell_meta['crs']}")
        if shell_meta.get("block_size_deg") is not None:
            notes.append(f"block_size_deg={shell_meta['block_size_deg']}")
        if shell_meta.get("local_evidence_only"):
            notes.append("local_evidence_only=true")

    if release_shell_enabled():
        from ssri_model.release_shell.evaluate import load_evaluation_summary

        evaluation_summary = load_evaluation_summary(checkpoint_path)

    aoi_source = None
    for note in acquisition_notes:
        if note.startswith("aoi_source="):
            aoi_source = note.split("=", 1)[1]
            break
    if aoi_source is None and body.features is not None:
        aoi_source = "offline_features"
    location_provenance = build_location_provenance(
        latitude=query_lat,
        longitude=query_lon,
        resolution_m=body.resolution_m,
        aoi_source=aoi_source,
        acquisition_meta=acquisition_meta,
    )
    if body.features is not None:
        location_provenance["notes"].append(
            "Offline feature tensor supplied; map point (if any) is used for region gating, "
            "not for raster sampling of the .npy stack."
        )
    notes.append(
        "location_provenance="
        + (
            f"submitted={query_lat},{query_lon}"
            if query_lat is not None and query_lon is not None
            else "none"
        )
    )
    grid = location_provenance.get("model_grid") or {}
    if grid.get("pixel_row") is not None and grid.get("pixel_col") is not None:
        notes.append(f"model_grid_pixel=row{grid['pixel_row']}_col{grid['pixel_col']}")

    advertised_names = schema_names
    if advertised_names is None and acquisition_meta and acquisition_meta.get("channel_names"):
        advertised_names = [str(n) for n in acquisition_meta["channel_names"]]
    conditioning_features = sample_conditioning_features(
        features,
        channel_names=advertised_names,
        pixel_row=grid.get("pixel_row") if isinstance(grid, dict) else None,
        pixel_col=grid.get("pixel_col") if isinstance(grid, dict) else None,
        aoi_source=aoi_source,
    )
    conditioning_features = enrich_conditioning_with_geological_catalogue(
        conditioning_features,
        output_root=output_root,
        latitude=query_lat,
        longitude=query_lon,
    )
    for layer_name, layer in (conditioning_features.get("layers") or {}).items():
        notes.append(
            f"conditioning_{layer_name}={layer.get('status')}"
            + (
                f":{layer.get('value')}"
                if layer.get("status") == "available" and layer.get("value") is not None
                else ""
            )
        )
    if conditioning_features.get("geological_context"):
        notes.append(
            "geological_context_count="
            + str(len(conditioning_features.get("geological_context") or []))
        )
    if spatial_url:
        notes.append(f"spatial_output_hazard={spatial_hazard}")
        notes.append(f"spatial_output_georef_quality={spatial_georef_quality}")

    response = AssessResponseBody(
        assessment_id=result.assessment_id,
        hazard_profiles=result_profiles,
        explanation=explanation,
        model_version=result.model_version,
        spatial_output_url=spatial_url,
        notes=notes,
        request_id=request_id,
        checkpoint_sha256=checkpoint_sha256,
        checkpoint_dataset_name=dataset_name,
        checkpoint_dataset_version=dataset_version,
        is_fixture_checkpoint=is_fixture,
        domain_similarity_calibrated=domain.calibrated,
        channel_schema_version=schema_version,
        channel_names=schema_names or advertised_names,
        checkpoint_id=checkpoint_path.stem if release_shell_enabled() else None,
        evaluation_summary=evaluation_summary,
        location_provenance=location_provenance,
        conditioning_features=conditioning_features,
        spatial_output_expires_seconds=spatial_expires,
        spatial_output_hazard=spatial_hazard,
        spatial_output_crs=spatial_crs,
        spatial_output_georef_quality=spatial_georef_quality,
        spatial_object_key=spatial_object_key,
    )
    _persist_assessment_response(
        output_root=output_root,
        assessment_id=assessment_id,
        body=response,
    )
    return response


def _history_coords(location_provenance: dict[str, Any] | None) -> tuple[float | None, float | None]:
    """Read WGS84 coords from persisted location_provenance without inventing values."""
    loc = location_provenance or {}
    lat = loc.get("latitude")
    lon = loc.get("longitude")
    if lat is None or lon is None:
        submitted = loc.get("submitted") if isinstance(loc.get("submitted"), dict) else {}
        lat = submitted.get("latitude", lat)
        lon = submitted.get("longitude", lon)
    try:
        return (
            float(lat) if lat is not None else None,
            float(lon) if lon is not None else None,
        )
    except (TypeError, ValueError):
        return None, None


def _history_summary_from_payload(
    assessment_id: str,
    data: dict[str, Any],
    *,
    modified_at: str,
) -> dict[str, Any]:
    loc = data.get("location_provenance") if isinstance(data.get("location_provenance"), dict) else {}
    lat, lon = _history_coords(loc)
    profiles = data.get("hazard_profiles") or []
    hazards = []
    for profile in profiles:
        if not isinstance(profile, dict):
            continue
        hazards.append(
            {
                "hazard_type": profile.get("hazard_type"),
                "point_estimate": profile.get("point_estimate"),
                "confidence_tier": profile.get("confidence_tier"),
            }
        )
    notes = data.get("notes") or []
    return {
        "assessment_id": assessment_id,
        "persisted": True,
        "modified_at": modified_at,
        "model_version": data.get("model_version"),
        "checkpoint_id": data.get("checkpoint_id"),
        "latitude": lat,
        "longitude": lon,
        "aoi_source": loc.get("aoi_source") if isinstance(loc, dict) else None,
        "hazards": hazards,
        "scientific_notes_present": any("NOT_VALIDATED" in str(n) for n in notes),
        "spatial_output_url": data.get("spatial_output_url"),
        "domain_similarity_calibrated": data.get("domain_similarity_calibrated"),
    }


@router.get("/history")
def list_assessment_history(
    limit: int = 50,
    offset: int = 0,
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_run_assess_rate_limited),
) -> dict[str, Any]:
    """List persisted filesystem assessments (assess_response.json).

    This is an operational archive index — not a scientific validation log.
    """
    del principal  # auth required; key_id not used for tenancy filtering yet
    limit = max(1, min(int(limit), 200))
    offset = max(0, int(offset))
    root = Path(service_config.output_root) / "assessments"
    items: list[dict[str, Any]] = []
    total = 0
    if root.is_dir():
        dirs = sorted(
            [p for p in root.iterdir() if p.is_dir() and p.name.startswith("assess-")],
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )
        total = len(dirs)
        for assess_dir in dirs[offset : offset + limit]:
            payload_path = assess_dir / "assess_response.json"
            modified_at = datetime.fromtimestamp(
                assess_dir.stat().st_mtime, tz=timezone.utc
            ).isoformat()
            entry: dict[str, Any] = {
                "assessment_id": assess_dir.name,
                "persisted": payload_path.is_file(),
                "modified_at": modified_at,
            }
            if payload_path.is_file():
                try:
                    data = json.loads(payload_path.read_text(encoding="utf-8"))
                    if isinstance(data, dict):
                        entry = _history_summary_from_payload(
                            assess_dir.name, data, modified_at=modified_at
                        )
                except Exception as exc:  # noqa: BLE001
                    entry["parse_error"] = str(exc)
            items.append(entry)
    return {
        "count": len(items),
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + limit) < total,
        "assessments": items,
        "retention": "filesystem under {output_root}/assessments/",
        "note": (
            "Operational history index only. Scores remain relative rankings; "
            "scientific_validation_status stays NOT_VALIDATED unless independently validated."
        ),
    }


@router.get("/history/{assessment_id}")
def get_assessment_history_detail(
    assessment_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_run_assess_rate_limited),
) -> dict[str, Any]:
    """Return one persisted assessment summary + available detail fields."""
    del principal
    _validate_assessment_id(assessment_id)
    assess_dir = Path(service_config.output_root) / "assessments" / assessment_id
    payload_path = assess_dir / "assess_response.json"
    if not payload_path.is_file():
        raise InvalidServiceRequestError(f"Assessment '{assessment_id}' was not found.")
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InvalidServiceRequestError("Assessment payload is not a JSON object.")
    modified_at = datetime.fromtimestamp(
        assess_dir.stat().st_mtime, tz=timezone.utc
    ).isoformat()
    summary = _history_summary_from_payload(
        assessment_id, data, modified_at=modified_at
    )
    return {
        "summary": summary,
        "assessment": {
            "assessment_id": data.get("assessment_id") or assessment_id,
            "model_version": data.get("model_version"),
            "checkpoint_id": data.get("checkpoint_id"),
            "checkpoint_sha256": data.get("checkpoint_sha256"),
            "hazard_profiles": data.get("hazard_profiles"),
            "location_provenance": data.get("location_provenance"),
            "notes": data.get("notes"),
            "explanation": data.get("explanation"),
            "spatial_output_url": data.get("spatial_output_url"),
            "domain_similarity_calibrated": data.get("domain_similarity_calibrated"),
            "conditioning_features": data.get("conditioning_features"),
        },
        "note": (
            "Persisted assess response. Scores are relative rankings; status remains "
            "NOT_VALIDATED unless independently validated."
        ),
        "spatial_download_path": (
            f"/api/v1/assess/history/{assessment_id}/spatial"
            if any(assess_dir.glob("*.tif"))
            or bool(data.get("spatial_output_url"))
            or bool(data.get("spatial_output_hazard"))
            else None
        ),
        "spatial_output_hazard": data.get("spatial_output_hazard"),
        "spatial_output_crs": data.get("spatial_output_crs"),
        "spatial_output_georef_quality": data.get("spatial_output_georef_quality"),
    }


def _validate_assessment_id(assessment_id: str) -> None:
    if (
        not assessment_id
        or ".." in assessment_id
        or "/" in assessment_id
        or "\\" in assessment_id
        or not assessment_id.startswith("assess-")
        or not all(ch.isalnum() or ch in "-_" for ch in assessment_id)
    ):
        raise InvalidServiceRequestError("Invalid assessment_id.")


def _resolve_assessment_geotiff(
    assess_dir: Path, data: dict[str, Any]
) -> Path:
    """Locate the on-disk GeoTIFF for an assessment (prefer hazard-named file)."""
    hazard = data.get("spatial_output_hazard")
    candidates: list[Path] = []
    if isinstance(hazard, str) and hazard:
        candidates.extend(
            [
                assess_dir / f"{hazard}_probability.tif",
                assess_dir / f"{hazard}_ranking_score.tif",
            ]
        )
    candidates.extend(sorted(assess_dir.glob("*.tif")))
    for path in candidates:
        if path.is_file():
            return path
    # Optional object-storage mirror under local backend root
    objects_dir = Path(assess_dir).parents[1] / "objects" / "assessments" / assess_dir.name
    if objects_dir.is_dir():
        for path in sorted(objects_dir.glob("*.tif")):
            if path.is_file():
                return path
    # Materialize from durable object key when local disk is empty (split services).
    object_key = data.get("spatial_object_key")
    if isinstance(object_key, str) and object_key.strip():
        try:
            from ssri_model.storage.durable import materialize_object_to_path

            hazard_name = (
                str(hazard)
                if isinstance(hazard, str) and hazard
                else "hazard"
            )
            dest = assess_dir / f"{hazard_name}_from_object_storage.tif"
            materialize_object_to_path(object_key.strip(), dest)
            if dest.is_file():
                return dest
        except Exception:
            pass
    raise InvalidServiceRequestError(
        "No GeoTIFF artefact is available for this assessment. "
        "Re-run with produce_geotiff=true."
    )


@router.get("/history/{assessment_id}/spatial")
def download_assessment_spatial(
    assessment_id: str,
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_run_assess_rate_limited),
) -> Response:
    """Authenticated GeoTIFF download for a persisted assessment.

    Prefer this over ``file://`` spatial_output_url values from local object storage,
    which browsers cannot fetch from an http(s) frontend origin.
    """
    del principal
    _validate_assessment_id(assessment_id)
    assess_dir = Path(service_config.output_root) / "assessments" / assessment_id
    payload_path = assess_dir / "assess_response.json"
    if not payload_path.is_file():
        raise InvalidServiceRequestError(f"Assessment '{assessment_id}' was not found.")
    data = json.loads(payload_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise InvalidServiceRequestError("Assessment payload is not a JSON object.")
    tif_path = _resolve_assessment_geotiff(assess_dir, data)
    return FileResponse(
        path=tif_path,
        media_type="image/tiff",
        filename=tif_path.name,
        headers={
            "Cache-Control": "no-store",
            "X-SSRI-Assessment-Id": assessment_id,
            "X-SSRI-Spatial-Hazard": str(data.get("spatial_output_hazard") or ""),
        },
    )
