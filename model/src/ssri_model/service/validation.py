"""Service validation and path safety utilities."""

from __future__ import annotations

import re
from pathlib import Path

from ssri_model.service.config import ServiceConfig
from ssri_model.service.exceptions import (
    InvalidServiceConfigError,
    InvalidServiceRequestError,
    OutputFormatError,
    PathSafetyError,
    ScientificGateError,
)
from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest
from ssri_model.service.schemas import GEOTIFF_ARTIFACTS, OutputFormat, SCIENTIFIC_VALIDATION_STATUSES

_SAFE_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


def reject_null_bytes(value: str, *, field_name: str) -> None:
    if "\x00" in value:
        raise PathSafetyError(f"{field_name} contains null bytes")


def sanitize_request_id(request_id: str) -> str:
    """Return a safe request identifier."""
    normalized = request_id.strip()
    reject_null_bytes(normalized, field_name="request_id")
    if not normalized:
        raise PathSafetyError("request_id must be non-empty")
    if ".." in normalized or "/" in normalized or "\\" in normalized:
        raise PathSafetyError(f"request_id contains unsafe path characters: {request_id!r}")
    if not _SAFE_REQUEST_ID_PATTERN.match(normalized):
        raise PathSafetyError(f"request_id is not a safe identifier: {request_id!r}")
    return normalized


def reject_path_traversal(path: str, *, field_name: str) -> None:
    reject_null_bytes(path, field_name=field_name)
    if ".." in path:
        raise PathSafetyError(f"{field_name} contains path traversal: {path!r}")


def resolve_under_output_root(output_root: Path | str, *parts: str) -> Path:
    """Resolve a path and ensure it remains under output_root."""
    root = Path(output_root).resolve()
    destination = root.joinpath(*parts).resolve()
    try:
        destination.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError(
            f"Resolved path {destination} is outside output_root {root}"
        ) from exc
    return destination


def ensure_output_under_root(path: Path | str, *, output_root: Path | str) -> Path:
    """Ensure an existing or intended output path is under output_root."""
    root = Path(output_root).resolve()
    candidate = Path(path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise PathSafetyError(
            f"Output path {candidate} is outside configured output_root {root}"
        ) from exc
    return candidate


def validate_output_format(output_format: OutputFormat | str) -> OutputFormat:
    if isinstance(output_format, OutputFormat):
        return output_format
    try:
        return OutputFormat(str(output_format))
    except ValueError as exc:
        raise OutputFormatError(f"Unsupported output format: {output_format!r}") from exc


def output_artifacts_for_format(output_format: OutputFormat) -> tuple[str, ...]:
    fmt = validate_output_format(output_format)
    if fmt in (OutputFormat.GEOTIFF, OutputFormat.ALL):
        return GEOTIFF_ARTIFACTS
    raise OutputFormatError(f"Unsupported output format: {fmt.value}")


def validate_service_config(config: ServiceConfig) -> ServiceConfig:
    """Validate service configuration values."""
    try:
        ServiceConfig.from_dict(config.to_dict())
    except InvalidServiceConfigError:
        raise
    except Exception as exc:
        raise InvalidServiceConfigError(str(exc)) from exc
    return config


def _validate_extension(path: str, *, allowed: tuple[str, ...], field_name: str) -> None:
    suffix = Path(path).suffix.lower()
    if suffix not in allowed:
        raise InvalidServiceRequestError(
            f"{field_name} extension {suffix!r} not in allowed set {allowed}"
        )


def _validate_existing_file(path: str, *, field_name: str) -> Path:
    reject_path_traversal(path, field_name=field_name)
    resolved = Path(path)
    if not resolved.is_file():
        raise InvalidServiceRequestError(f"{field_name} not found or not a file: {path}")
    return resolved


def resolve_request_scientific_status(
    claimed: str,
    *,
    trust_client_scientific_status: bool,
) -> str:
    """Resolve client-supplied scientific status for server-side policy.

    Clients must never be able to self-assert ``SCIENTIFICALLY_VALIDATED``.
    When ``trust_client_scientific_status`` is False (production default),
    all client-supplied statuses are ignored and treated as ``NOT_VALIDATED``.
    Intermediate audit statuses may be accepted only when explicitly trusted
    (development/test).
    """
    if claimed not in SCIENTIFIC_VALIDATION_STATUSES:
        raise InvalidServiceRequestError(
            f"Unsupported scientific_validation_status: {claimed!r}"
        )
    if claimed == "SCIENTIFICALLY_VALIDATED":
        raise InvalidServiceRequestError(
            "SCIENTIFICALLY_VALIDATED cannot be asserted by API clients; "
            "status must be established by server-side validation records."
        )
    if not trust_client_scientific_status:
        return "NOT_VALIDATED"
    return claimed


def can_serve_prediction(
    scientific_validation_status: str,
    *,
    allow_unvalidated_predictions: bool,
    scientific_validation_required: bool,
) -> bool:
    """Determine whether a prediction may be served under policy rules.

    Operational inference success is not geological validation.
    This function never upgrades scientific status.
    """
    if scientific_validation_status not in SCIENTIFIC_VALIDATION_STATUSES:
        return False
    if scientific_validation_required:
        return scientific_validation_status == "SCIENTIFICALLY_VALIDATED"
    if not allow_unvalidated_predictions:
        return scientific_validation_status != "NOT_VALIDATED"
    return True


def enforce_scientific_gate(
    scientific_validation_status: str,
    *,
    allow_unvalidated_predictions: bool,
    scientific_validation_required: bool,
) -> None:
    if not can_serve_prediction(
        scientific_validation_status,
        allow_unvalidated_predictions=allow_unvalidated_predictions,
        scientific_validation_required=scientific_validation_required,
    ):
        raise ScientificGateError(
            "Prediction serving blocked by scientific validation policy; "
            f"status={scientific_validation_status!r}"
        )


def validate_inference_request(
    request: InferenceRequest,
    config: ServiceConfig,
    *,
    scientific_validation_status: str = "NOT_VALIDATED",
) -> Path:
    """Early boundary validation for a single inference request."""
    safe_id = sanitize_request_id(request.request_id)
    _validate_existing_file(request.checkpoint, field_name="checkpoint")
    features = _validate_existing_file(request.features, field_name="features")
    _validate_existing_file(request.manifest, field_name="manifest")
    _validate_existing_file(request.statistics, field_name="statistics")

    _validate_extension(
        request.features,
        allowed=config.allowed_feature_extensions,
        field_name="features",
    )
    _validate_extension(
        request.manifest,
        allowed=config.allowed_manifest_extensions,
        field_name="manifest",
    )
    _validate_extension(
        request.statistics,
        allowed=config.allowed_manifest_extensions,
        field_name="statistics",
    )

    if features.stat().st_size > config.max_input_size:
        raise InvalidServiceRequestError(
            f"features file exceeds max_input_size ({config.max_input_size} bytes)"
        )

    tile_size = request.tile_size or config.default_inference_tile_size
    overlap = request.overlap if request.overlap is not None else config.default_inference_overlap
    batch_size = request.batch_size or config.default_batch_size

    if tile_size <= 0:
        raise InvalidServiceRequestError("tile_size must be positive")
    if overlap < 0:
        raise InvalidServiceRequestError("overlap must be non-negative")
    if overlap >= tile_size:
        raise InvalidServiceRequestError("overlap must be less than tile_size")
    if batch_size <= 0:
        raise InvalidServiceRequestError("batch_size must be positive")

    validate_output_format(request.output_format)

    if request.output_dir:
        reject_path_traversal(request.output_dir, field_name="output_dir")
        output_dir = ensure_output_under_root(request.output_dir, output_root=config.output_root)
    else:
        output_dir = resolve_under_output_root(config.output_root, "requests", safe_id)

    enforce_scientific_gate(
        scientific_validation_status,
        allow_unvalidated_predictions=config.allow_unvalidated_predictions,
        scientific_validation_required=(
            config.scientific_validation_required or request.scientific_validation_required
        ),
    )

    return output_dir


def validate_batch_request(
    request: BatchInferenceRequest,
    config: ServiceConfig,
    *,
    scientific_validation_status: str = "NOT_VALIDATED",
) -> Path:
    """Early boundary validation for a batch inference request."""
    sanitize_request_id(request.request_id)
    jobs_file = _validate_existing_file(request.jobs_file, field_name="jobs_file")
    _validate_extension(
        request.jobs_file,
        allowed=config.allowed_manifest_extensions,
        field_name="jobs_file",
    )

    reject_path_traversal(request.output_root, field_name="output_root")
    output_root = ensure_output_under_root(request.output_root, output_root=config.output_root)

    if jobs_file.stat().st_size > config.max_input_size:
        raise InvalidServiceRequestError(
            f"jobs_file exceeds max_input_size ({config.max_input_size} bytes)"
        )

    enforce_scientific_gate(
        scientific_validation_status,
        allow_unvalidated_predictions=config.allow_unvalidated_predictions,
        scientific_validation_required=config.scientific_validation_required,
    )

    return output_root
