"""SSRI operational service contracts."""

from ssri_model.service.config import ServiceConfig
from ssri_model.service.exceptions import (
    InvalidServiceConfigError,
    InvalidServiceRequestError,
    OutputFormatError,
    PathSafetyError,
    ScientificGateError,
    ServiceError,
)
from ssri_model.service.provenance import ProvenanceRecord, build_provenance_record
from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest
from ssri_model.service.responses import BatchInferenceResponse, InferenceResponse
from ssri_model.service.schemas import (
    BatchExecutionStatus,
    GEOTIFF_ARTIFACTS,
    InferenceExecutionStatus,
    OutputFormat,
    SCIENTIFIC_VALIDATION_STATUSES,
    ServiceEnvironment,
)
from ssri_model.service.validation import (
    can_serve_prediction,
    enforce_scientific_gate,
    ensure_output_under_root,
    output_artifacts_for_format,
    reject_null_bytes,
    reject_path_traversal,
    resolve_request_scientific_status,
    resolve_under_output_root,
    sanitize_request_id,
    validate_batch_request,
    validate_inference_request,
    validate_output_format,
    validate_service_config,
)

__all__ = [
    "BatchExecutionStatus",
    "BatchInferenceRequest",
    "BatchInferenceResponse",
    "GEOTIFF_ARTIFACTS",
    "InferenceExecutionStatus",
    "InferenceRequest",
    "InferenceResponse",
    "InvalidServiceConfigError",
    "InvalidServiceRequestError",
    "OutputFormat",
    "OutputFormatError",
    "PathSafetyError",
    "ProvenanceRecord",
    "SCIENTIFIC_VALIDATION_STATUSES",
    "ScientificGateError",
    "ServiceConfig",
    "ServiceEnvironment",
    "ServiceError",
    "build_provenance_record",
    "can_serve_prediction",
    "enforce_scientific_gate",
    "ensure_output_under_root",
    "output_artifacts_for_format",
    "reject_null_bytes",
    "reject_path_traversal",
    "resolve_request_scientific_status",
    "resolve_under_output_root",
    "sanitize_request_id",
    "validate_batch_request",
    "validate_inference_request",
    "validate_output_format",
    "validate_service_config",
]
