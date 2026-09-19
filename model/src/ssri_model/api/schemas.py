"""Pydantic schemas for SSRI HTTP API."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest
from ssri_model.service.responses import BatchInferenceResponse, InferenceResponse
from ssri_model.service.schemas import OutputFormat


class InferenceRequestBody(BaseModel):
    """HTTP request body for single inference."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    checkpoint: str
    features: str
    manifest: str
    statistics: str
    output_dir: str = ""
    output_format: OutputFormat = OutputFormat.ALL
    tile_size: int | None = None
    overlap: int | None = None
    batch_size: int | None = None
    scientific_validation_required: bool = False
    scientific_validation_status: str = "NOT_VALIDATED"

    def to_service_request(self) -> InferenceRequest:
        return InferenceRequest(
            request_id=self.request_id,
            checkpoint=self.checkpoint,
            features=self.features,
            manifest=self.manifest,
            statistics=self.statistics,
            output_dir=self.output_dir,
            output_format=self.output_format,
            tile_size=self.tile_size,
            overlap=self.overlap,
            batch_size=self.batch_size,
            scientific_validation_required=self.scientific_validation_required,
        )


class BatchInferenceRequestBody(BaseModel):
    """HTTP request body for batch inference."""

    model_config = ConfigDict(extra="forbid")

    request_id: str
    jobs_file: str
    output_root: str
    resume: bool = False
    scientific_validation_status: str = "NOT_VALIDATED"

    def to_service_request(self) -> BatchInferenceRequest:
        return BatchInferenceRequest(
            request_id=self.request_id,
            jobs_file=self.jobs_file,
            output_root=self.output_root,
            resume=self.resume,
        )


class ProvenanceResponse(BaseModel):
    """Provenance metadata returned with inference responses."""

    request_id: str
    checkpoint_path: str
    features_path: str
    manifest_path: str
    statistics_path: str
    dataset_name: str | None = None
    dataset_version: str | None = None
    dataset_fingerprint: str = ""
    statistics_fingerprint: str = ""
    checkpoint_fingerprint: str = ""
    configuration_fingerprint: str = ""
    combined_fingerprint: str = ""
    inference_configuration: dict[str, Any] = Field(default_factory=dict)
    scientific_validation_status: str = "NOT_VALIDATED"
    service_name: str = "ssri-inference"
    service_version: str = "0.1.0"
    created_at: str = ""
    auth_key_id: str | None = None
    auth_role: str | None = None
    auth_method: str | None = None

    @classmethod
    def from_record(cls, record: Any) -> ProvenanceResponse:
        return cls(**record.to_dict())


class InferenceResponseBody(BaseModel):
    """HTTP response body for single inference."""

    request_id: str
    status: str
    prediction_path: str | None = None
    confidence_path: str | None = None
    probability_path: str | None = None
    metadata_path: str | None = None
    model_version: str | None = None
    dataset_name: str | None = None
    dataset_version: str | None = None
    scientific_validation_status: str = "NOT_VALIDATED"
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None
    provenance: ProvenanceResponse | None = None

    @classmethod
    def from_service_response(
        cls,
        response: InferenceResponse,
        *,
        provenance: ProvenanceResponse | None = None,
    ) -> InferenceResponseBody:
        return cls(
            request_id=response.request_id,
            status=response.status.value,
            prediction_path=response.prediction_path,
            confidence_path=response.confidence_path,
            probability_path=response.probability_path,
            metadata_path=response.metadata_path,
            model_version=response.model_version,
            dataset_name=response.dataset_name,
            dataset_version=response.dataset_version,
            scientific_validation_status=response.scientific_validation_status,
            started_at=response.started_at,
            completed_at=response.completed_at,
            error=response.error,
            provenance=provenance,
        )


class BatchInferenceResponseBody(BaseModel):
    """HTTP response body for batch inference."""

    request_id: str
    batch_id: str
    status: str
    total_jobs: int = 0
    completed_jobs: int = 0
    failed_jobs: int = 0
    skipped_jobs: int = 0
    manifest_path: str | None = None
    output_root: str | None = None
    scientific_validation_status: str = "NOT_VALIDATED"
    started_at: str | None = None
    completed_at: str | None = None
    error: str | None = None

    @classmethod
    def from_service_response(
        cls,
        response: BatchInferenceResponse,
        *,
        output_root: str | None = None,
    ) -> BatchInferenceResponseBody:
        return cls(
            request_id=response.request_id,
            batch_id=response.batch_id,
            status=response.status.value,
            total_jobs=response.total_jobs,
            completed_jobs=response.completed_jobs,
            failed_jobs=response.failed_jobs,
            skipped_jobs=response.skipped_jobs,
            manifest_path=response.manifest_path,
            output_root=output_root,
            scientific_validation_status=response.scientific_validation_status,
            started_at=response.started_at,
            completed_at=response.completed_at,
            error=response.error,
        )


class HealthResponse(BaseModel):
    status: str
    service: str


class ReadinessResponse(BaseModel):
    status: str
    service: str
    infrastructure: dict[str, object] | None = None


class BatchStatusResponseBody(BaseModel):
    batch_id: str
    status: str
    total_jobs: int
    completed_jobs: int
    failed_jobs: int
    skipped_jobs: int
    pending_jobs: int = 0
    running_jobs: int = 0
    manifest_path: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class JobStatusResponseBody(BaseModel):
    batch_id: str
    job_id: str
    status: str
    output_dir: str
    error_type: str | None = None
    error_message: str | None = None
    started_at: str | None = None
    completed_at: str | None = None


class InferenceMetadataResponseBody(BaseModel):
    request_id: str
    status: str
    scientific_validation_status: str
    provenance: ProvenanceResponse
    artifacts: dict[str, str | None] = Field(default_factory=dict)


class CreateAPIKeyRequestBody(BaseModel):
    role: str
    name: str = ""
    expires_at: str | None = None


class CreateAPIKeyResponseBody(BaseModel):
    key_id: str
    api_key: str
    role: str
    name: str = ""
    expires_at: str | None = None
    created_at: str
    message: str = "Store this API key securely. It cannot be retrieved later."


class APIKeySummaryBody(BaseModel):
    key_id: str
    role: str
    enabled: bool
    name: str = ""
    expires_at: str | None = None
    created_at: str = ""


class AsyncJobSubmissionResponseBody(BaseModel):
    job_id: str
    request_id: str
    status: str
    scientific_validation_status: str
    status_url: str


class JobDetailResponseBody(BaseModel):
    job_id: str
    request_id: str
    job_type: str
    status: str
    scientific_validation_status: str
    created_at: str
    started_at: str | None = None
    completed_at: str | None = None
    submitted_by_key_id: str
    auth_role: str
    artifacts: dict[str, Any] = Field(default_factory=dict)
    error_code: str | None = None
    error_message: str | None = None

