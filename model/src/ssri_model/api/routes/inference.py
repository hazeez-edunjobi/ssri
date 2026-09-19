"""Single inference API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Request

from ssri_model.api.dependencies import (
    InferenceExecutor,
    get_app_state,
    get_inference_executor,
    get_job_executor,
    get_job_service,
    get_service_config,
    load_inference_metadata,
    require_read_metadata,
    require_run_inference_rate_limited,
)
from ssri_model.api.job_workers import run_inference_job
from ssri_model.api.schemas import (
    AsyncJobSubmissionResponseBody,
    InferenceMetadataResponseBody,
    InferenceRequestBody,
    InferenceResponseBody,
    ProvenanceResponse,
)
from ssri_model.auth.models import AuthenticatedPrincipal
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.models import JobType
from ssri_model.jobs.service import JobService
from ssri_model.orchestration.exceptions import BatchManifestError
from ssri_model.service.config import ServiceConfig
from ssri_model.service.provenance import ProvenanceRecord
from ssri_model.service.validation import (
    validate_inference_request,
    resolve_request_scientific_status,
)

router = APIRouter(prefix="/inference", tags=["inference"])


@router.post("", response_model=InferenceResponseBody, status_code=200)
def run_inference_endpoint(
    body: InferenceRequestBody,
    executor: InferenceExecutor = Depends(get_inference_executor),
    service_config: ServiceConfig = Depends(get_service_config),
    principal: AuthenticatedPrincipal = Depends(require_run_inference_rate_limited),
) -> InferenceResponseBody:
    request = body.to_service_request()
    scientific_status = resolve_request_scientific_status(
        body.scientific_validation_status,
        trust_client_scientific_status=service_config.trust_client_scientific_status,
    )
    response, provenance = executor.execute(
        request,
        scientific_validation_status=scientific_status,
        principal=principal,
    )
    return InferenceResponseBody.from_service_response(
        response,
        provenance=ProvenanceResponse.from_record(provenance),
    )


@router.post("/async", response_model=AsyncJobSubmissionResponseBody, status_code=202)
def run_inference_async_endpoint(
    body: InferenceRequestBody,
    request: Request,
    service_config: ServiceConfig = Depends(get_service_config),
    executor: InferenceExecutor = Depends(get_inference_executor),
    job_service: JobService = Depends(get_job_service),
    job_executor: JobExecutor = Depends(get_job_executor),
    principal: AuthenticatedPrincipal = Depends(require_run_inference_rate_limited),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AsyncJobSubmissionResponseBody:
    service_request = body.to_service_request()
    scientific_status = resolve_request_scientific_status(
        body.scientific_validation_status,
        trust_client_scientific_status=service_config.trust_client_scientific_status,
    )
    validate_inference_request(
        service_request,
        service_config,
        scientific_validation_status=scientific_status,
    )
    payload = body.model_dump()
    payload["scientific_validation_status"] = scientific_status
    record = job_service.create_job(
        request_id=service_request.request_id,
        job_type=JobType.INFERENCE,
        principal=principal,
        scientific_validation_status=scientific_status,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    if record.status.value == "queued":
        job_executor.submit(
            record.job_id,
            lambda: run_inference_job(
                job_service=job_service,
                inference_executor=executor,
                job_id=record.job_id,
                request=service_request,
                scientific_validation_status=scientific_status,
                principal_key_id=principal.key_id,
                auth_role=principal.role.value,
            ),
        )
    api_prefix = get_app_state(request).api_config.api_prefix
    return AsyncJobSubmissionResponseBody(
        job_id=record.job_id,
        request_id=record.request_id,
        status=record.status.value,
        scientific_validation_status=record.scientific_validation_status,
        status_url=f"{api_prefix}/jobs/{record.job_id}",
    )


@router.get("/{request_id}", response_model=InferenceMetadataResponseBody)
def get_inference_metadata(
    request_id: str,
    output_dir: str | None = None,
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_metadata),
) -> InferenceMetadataResponseBody:
    try:
        payload = load_inference_metadata(
            service_config=service_config,
            request_id=request_id,
            output_dir=output_dir,
        )
    except BatchManifestError:
        raise
    metadata = payload["metadata"]
    provenance = ProvenanceRecord.from_dict(payload["provenance"])
    return InferenceMetadataResponseBody(
        request_id=str(metadata.get("request_id", request_id)),
        status=str(metadata.get("status", "unknown")),
        scientific_validation_status=str(
            metadata.get("scientific_validation_status", "NOT_VALIDATED")
        ),
        provenance=ProvenanceResponse.from_record(provenance),
        artifacts=dict(metadata.get("artifacts", {})),
    )
