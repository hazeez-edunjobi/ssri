"""Batch inference API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header, Query, Request

from ssri_model.api.dependencies import (
    BatchExecutor,
    fetch_batch_status,
    fetch_job_status,
    get_app_state,
    get_batch_executor,
    get_job_executor,
    get_job_service,
    get_service_config,
    require_read_status_rate_limited,
    require_run_batch_rate_limited,
)
from ssri_model.api.job_workers import run_batch_job
from ssri_model.api.schemas import (
    AsyncJobSubmissionResponseBody,
    BatchInferenceRequestBody,
    BatchInferenceResponseBody,
    BatchStatusResponseBody,
    JobStatusResponseBody,
)
from ssri_model.auth.models import AuthenticatedPrincipal
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.models import JobType
from ssri_model.jobs.service import JobService
from ssri_model.service.config import ServiceConfig
from ssri_model.service.validation import (
    resolve_request_scientific_status,
    validate_batch_request,
)
router = APIRouter(prefix="/batch", tags=["batch"])


@router.post("", response_model=BatchInferenceResponseBody, status_code=200)
def run_batch_endpoint(
    body: BatchInferenceRequestBody,
    executor: BatchExecutor = Depends(get_batch_executor),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_run_batch_rate_limited),
) -> BatchInferenceResponseBody:
    request = body.to_service_request()
    scientific_status = resolve_request_scientific_status(
        body.scientific_validation_status,
        trust_client_scientific_status=service_config.trust_client_scientific_status,
    )
    response = executor.execute(
        request,
        scientific_validation_status=scientific_status,
    )
    return BatchInferenceResponseBody.from_service_response(
        response,
        output_root=request.output_root,
    )


@router.post("/async", response_model=AsyncJobSubmissionResponseBody, status_code=202)
def run_batch_async_endpoint(
    body: BatchInferenceRequestBody,
    request: Request,
    service_config: ServiceConfig = Depends(get_service_config),
    executor: BatchExecutor = Depends(get_batch_executor),
    job_service: JobService = Depends(get_job_service),
    job_executor: JobExecutor = Depends(get_job_executor),
    principal: AuthenticatedPrincipal = Depends(require_run_batch_rate_limited),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> AsyncJobSubmissionResponseBody:
    service_request = body.to_service_request()
    scientific_status = resolve_request_scientific_status(
        body.scientific_validation_status,
        trust_client_scientific_status=service_config.trust_client_scientific_status,
    )
    validate_batch_request(
        service_request,
        service_config,
        scientific_validation_status=scientific_status,
    )
    payload = body.model_dump()
    payload["scientific_validation_status"] = scientific_status
    record = job_service.create_job(
        request_id=service_request.request_id,
        job_type=JobType.BATCH,
        principal=principal,
        scientific_validation_status=scientific_status,
        payload=payload,
        idempotency_key=idempotency_key,
    )
    if record.status.value == "queued":
        job_executor.submit(
            record.job_id,
            lambda: run_batch_job(
                job_service=job_service,
                batch_executor=executor,
                job_id=record.job_id,
                request=service_request,
                scientific_validation_status=scientific_status,
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


@router.get("/{batch_id}/status", response_model=BatchStatusResponseBody)
def batch_status_endpoint(
    batch_id: str,
    output_root: str | None = Query(default=None),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status_rate_limited),
) -> BatchStatusResponseBody:
    payload = fetch_batch_status(
        service_config=service_config,
        batch_id=batch_id,
        output_root=output_root,
    )
    return BatchStatusResponseBody(**payload)


@router.get("/{batch_id}/jobs/{job_id}", response_model=JobStatusResponseBody)
def job_status_endpoint(
    batch_id: str,
    job_id: str,
    output_root: str | None = Query(default=None),
    service_config: ServiceConfig = Depends(get_service_config),
    _principal: AuthenticatedPrincipal = Depends(require_read_status_rate_limited),
) -> JobStatusResponseBody:
    payload = fetch_job_status(
        service_config=service_config,
        batch_id=batch_id,
        job_id=job_id,
        output_root=output_root,
    )
    return JobStatusResponseBody(**payload)
