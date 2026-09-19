"""Background job workers for async API execution."""

from __future__ import annotations

from ssri_model.api.dependencies import BatchExecutor, InferenceExecutor
from ssri_model.jobs.service import JobService
from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest


def run_inference_job(
    *,
    job_service: JobService,
    inference_executor: InferenceExecutor,
    job_id: str,
    request: InferenceRequest,
    scientific_validation_status: str,
    principal_key_id: str,
    auth_role: str,
) -> None:
    from ssri_model.auth.models import AuthenticatedPrincipal, Role
    from ssri_model.auth.authorization import permissions_for_role

    principal = AuthenticatedPrincipal(
        key_id=principal_key_id,
        role=Role(auth_role),
        permissions=permissions_for_role(Role(auth_role)),
        authentication_method="api_key",
        authenticated_at="",
    )
    try:
        response, provenance = inference_executor.execute(
            request,
            scientific_validation_status=scientific_validation_status,
            principal=principal,
        )
        job_service.mark_completed(
            job_id,
            result={
                "request_id": response.request_id,
                "status": response.status.value,
                "prediction_path": response.prediction_path,
                "confidence_path": response.confidence_path,
                "probability_path": response.probability_path,
                "metadata_path": response.metadata_path,
                "scientific_validation_status": response.scientific_validation_status,
                "provenance": provenance.to_dict(),
            },
        )
    except Exception:
        job_service.mark_failed(
            job_id,
            error_code="INFERENCE_FAILED",
            error_message="Inference job failed.",
        )


def run_batch_job(
    *,
    job_service: JobService,
    batch_executor: BatchExecutor,
    job_id: str,
    request: BatchInferenceRequest,
    scientific_validation_status: str,
) -> None:
    try:
        response = batch_executor.execute(
            request,
            scientific_validation_status=scientific_validation_status,
        )
        job_service.mark_completed(
            job_id,
            result={
                "request_id": response.request_id,
                "batch_id": response.batch_id,
                "status": response.status.value,
                "total_jobs": response.total_jobs,
                "completed_jobs": response.completed_jobs,
                "failed_jobs": response.failed_jobs,
                "skipped_jobs": response.skipped_jobs,
                "manifest_path": response.manifest_path,
                "scientific_validation_status": response.scientific_validation_status,
            },
        )
    except Exception:
        job_service.mark_failed(
            job_id,
            error_code="BATCH_FAILED",
            error_message="Batch job failed.",
        )
