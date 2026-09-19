"""Async job API routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from ssri_model.api.dependencies import (
    get_job_executor,
    get_job_service,
    require_read_status,
    require_run_inference,
)
from ssri_model.api.schemas import JobDetailResponseBody
from ssri_model.auth.models import AuthenticatedPrincipal, Role
from ssri_model.jobs.exceptions import JobAccessDeniedError, JobCannotCancelError, JobNotFoundError
from ssri_model.jobs.executor import JobExecutor
from ssri_model.jobs.models import JobRecord, JobStatus
from ssri_model.jobs.service import JobService

router = APIRouter(prefix="/jobs", tags=["jobs"])


def _job_to_response(record: JobRecord) -> JobDetailResponseBody:
    artifacts: dict[str, object] = {}
    if record.status == JobStatus.COMPLETED:
        result = record.result or {}
        artifacts = {
            "prediction": result.get("prediction_path"),
            "confidence": result.get("confidence_path"),
            "probabilities": result.get("probability_path"),
            "metadata": result.get("metadata_path"),
            "manifest_path": result.get("manifest_path"),
        }
    return JobDetailResponseBody(
        job_id=record.job_id,
        request_id=record.request_id,
        job_type=record.job_type.value,
        status=record.status.value,
        scientific_validation_status=record.scientific_validation_status,
        created_at=record.created_at,
        started_at=record.started_at,
        completed_at=record.completed_at,
        submitted_by_key_id=record.submitted_by_key_id,
        auth_role=record.auth_role,
        artifacts=artifacts,
        error_code=record.error_code,
        error_message=record.error_message,
    )


@router.get("/{job_id}", response_model=JobDetailResponseBody)
def get_job_status_endpoint(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    principal: AuthenticatedPrincipal = Depends(require_read_status),
) -> JobDetailResponseBody:
    try:
        record = job_service.get_job(job_id, principal=principal)
    except JobAccessDeniedError as exc:
        raise JobNotFoundError("Job not found") from exc
    return _job_to_response(record)


@router.post("/{job_id}/cancel", response_model=JobDetailResponseBody)
def cancel_job_endpoint(
    job_id: str,
    job_service: JobService = Depends(get_job_service),
    job_executor: JobExecutor = Depends(get_job_executor),
    principal: AuthenticatedPrincipal = Depends(require_run_inference),
) -> JobDetailResponseBody:
    record = job_service.get_job(job_id, principal=principal)
    if record.submitted_by_key_id != principal.key_id and principal.role != Role.ADMIN:
        raise JobNotFoundError("Job not found")
    try:
        cancelled = job_executor.cancel(job_id)
    except JobCannotCancelError as exc:
        raise exc
    return _job_to_response(cancelled)
