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


def run_training_job(
    *,
    job_service: JobService,
    job_id: str,
    payload: dict,
) -> None:
    """Execute a manual Stage 2.5 training job."""
    from ssri_model.manual_training.exceptions import ManualTrainingError
    from ssri_model.manual_training.registry import ModelRegistry
    from ssri_model.manual_training.runner import run_manual_training
    from ssri_model.manual_training.storage import TrainingStorage

    output_root = str(payload.get("output_root") or "outputs/service")
    storage = TrainingStorage(output_root)
    registry = ModelRegistry(storage)
    try:
        result = run_manual_training(
            storage=storage,
            registry=registry,
            dataset_id=str(payload["dataset_id"]),
            run_id=str(payload["run_id"]),
            job_id=job_id,
            epochs=int(payload.get("epochs", 20)),
            batch_size=int(payload.get("batch_size", 4)),
            learning_rate=float(payload.get("learning_rate", 1e-3)),
            seed=int(payload.get("seed", 42)),
            early_stopping_patience=payload.get("early_stopping_patience"),
            model_name=payload.get("model_name"),
            device=str(payload.get("device", "cpu")),
        )
        job_service.mark_completed(job_id, result=result)
    except ManualTrainingError as exc:
        storage.write_progress(
            str(payload.get("run_id") or "unknown"),
            {
                "phase": "failed",
                "message": exc.message,
                "error_code": exc.code,
            },
        )
        job_service.mark_failed(
            job_id,
            error_code=exc.code,
            error_message=exc.message,
        )
    except Exception:
        job_service.mark_failed(
            job_id,
            error_code="TRAINING_FAILED",
            error_message=(
                "Training failed unexpectedly. See server logs for technical details."
            ),
        )
