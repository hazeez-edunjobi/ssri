"""Distributed worker job execution and recovery."""

from __future__ import annotations

import random
import socket
import os
import time

from ssri_model.api.config import APIConfig
from ssri_model.infrastructure.config import InfrastructureConfig
from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.factory import build_infrastructure
from ssri_model.infrastructure.observability import log_operational_event
from ssri_model.infrastructure.redis.queue import RedisJobQueue
from ssri_model.infrastructure.retry import attempts_remaining, is_retryable_failure
from ssri_model.infrastructure.worker.heartbeat import HeartbeatController
from ssri_model.infrastructure.worker.lifecycle import request_worker_shutdown, worker_shutdown_requested
from ssri_model.jobs.exceptions import JobNotFoundError
from ssri_model.jobs.models import JobStatus, JobType
from ssri_model.jobs.service import JobService, utc_now_iso
from ssri_model.jobs.transitions import is_terminal
from ssri_model.worker.celery_app import get_celery_app

logger = __import__("logging").getLogger(__name__)


def worker_id() -> str:
    return f"{socket.gethostname()}-{os.getpid()}"


def _build_worker_context() -> tuple[APIConfig, JobService, DatabaseJobStore, RedisJobQueue, InfrastructureConfig]:
    api_config = APIConfig.from_env()
    resources = build_infrastructure(api_config)
    store = resources.job_store
    if not isinstance(store, DatabaseJobStore):
        raise RuntimeError("Distributed worker requires DatabaseJobStore")
    if resources.redis_client is None:
        raise RuntimeError("Distributed worker requires Redis")
    queue = RedisJobQueue(resources.redis_client)
    return api_config, resources.job_service, store, queue, api_config.infrastructure_config


def _retry_delay(infra: InfrastructureConfig, attempt: int) -> float:
    base = min(
        infra.retry_backoff_seconds * (2 ** max(0, attempt - 1)),
        infra.retry_backoff_max_seconds,
    )
    return float(base + random.uniform(0, infra.retry_jitter_seconds))


def _safe_ack(queue: RedisJobQueue, job_id: str) -> None:
    queue.acknowledge(job_id)


def _requeue_for_retry(
    *,
    store: DatabaseJobStore,
    queue: RedisJobQueue,
    infra: InfrastructureConfig,
    job_id: str,
    attempt: int,
) -> None:
    store.transition(job_id, target=JobStatus.QUEUED, expected=JobStatus.FAILED)
    queue.requeue(job_id)
    delay = _retry_delay(infra, attempt)
    log_operational_event(
        "job_requeued",
        job_id=job_id,
        attempt=attempt,
        delay_seconds=delay,
    )
    time.sleep(delay)
    get_celery_app().send_task(infra.celery_task_name, args=[job_id])


def execute_job_record(job_id: str) -> None:
    """Execute a durable job outside the API process."""
    from ssri_model.api.dependencies import DefaultBatchExecutor, DefaultInferenceExecutor
    from ssri_model.api.job_workers import run_batch_job, run_inference_job
    from ssri_model.service.requests import BatchInferenceRequest, InferenceRequest

    if worker_shutdown_requested():
        log_operational_event("worker_shutdown", job_id=job_id, phase="skip_new_work")
        return

    api_config, job_service, store, queue, infra = _build_worker_context()
    wid = worker_id()

    try:
        existing = store.load(job_id)
    except JobNotFoundError:
        log_operational_event("job_claim_skipped", job_id=job_id, reason="not_found")
        _safe_ack(queue, job_id)
        return

    if is_terminal(existing.status):
        log_operational_event("job_claim_skipped", job_id=job_id, reason="terminal")
        _safe_ack(queue, job_id)
        return

    now = utc_now_iso()
    claimed = store.claim(job_id, worker_id=wid, started_at=now, heartbeat_at=now)
    if claimed is None:
        current = store.load(job_id)
        if is_terminal(current.status):
            _safe_ack(queue, job_id)
        log_operational_event("job_claim_skipped", job_id=job_id, reason="not_claimable")
        return
    if claimed.status == JobStatus.CANCELLED:
        _safe_ack(queue, job_id)
        return

    log_operational_event(
        "job_claimed",
        job_id=job_id,
        worker_id=wid,
        attempt=claimed.attempt,
        request_id=claimed.request_id,
    )

    heartbeat = HeartbeatController(
        store,
        job_id=job_id,
        worker_id=wid,
        interval_seconds=float(infra.worker_heartbeat_seconds),
        should_continue=lambda: not worker_shutdown_requested(),
    )
    heartbeat.start(initial_heartbeat=now, initial_version=claimed.version)

    inference_executor = DefaultInferenceExecutor(api_config.service_config)
    batch_executor = DefaultBatchExecutor(api_config.service_config)

    try:
        if claimed.cancel_requested or worker_shutdown_requested():
            store.transition(job_id, target=JobStatus.CANCELLED, expected=JobStatus.RUNNING)
            _safe_ack(queue, job_id)
            log_operational_event("job_cancelled", job_id=job_id, worker_id=wid)
            return
        if claimed.job_type == JobType.INFERENCE:
            request = InferenceRequest.from_dict(claimed.payload)
            run_inference_job(
                job_service=job_service,
                inference_executor=inference_executor,
                job_id=job_id,
                request=request,
                scientific_validation_status=claimed.scientific_validation_status,
                principal_key_id=claimed.submitted_by_key_id,
                auth_role=claimed.auth_role,
            )
        else:
            batch_request = BatchInferenceRequest.from_dict(claimed.payload)
            run_batch_job(
                job_service=job_service,
                batch_executor=batch_executor,
                job_id=job_id,
                request=batch_request,
                scientific_validation_status=claimed.scientific_validation_status,
            )
        final = store.load(job_id)
        if final.status == JobStatus.COMPLETED:
            _safe_ack(queue, job_id)
            log_operational_event("job_completed", job_id=job_id, worker_id=wid)
            return
        if (
            final.status == JobStatus.FAILED
            and attempts_remaining(attempt=final.attempt, max_attempts=final.max_attempts)
        ):
            _requeue_for_retry(
                store=store,
                queue=queue,
                infra=infra,
                job_id=job_id,
                attempt=final.attempt,
            )
            return
        _safe_ack(queue, job_id)
    except Exception as exc:
        if not is_retryable_failure(exc):
            job_service.mark_failed(
                job_id,
                error_code="NON_RETRYABLE_FAILURE",
                error_message="Job failed with a non-retryable error.",
            )
            _safe_ack(queue, job_id)
            log_operational_event("job_failed", job_id=job_id, worker_id=wid, retryable=False)
            return
        logger.exception("Worker failed executing job %s", job_id)
        job_service.mark_failed(
            job_id,
            error_code="JOB_EXECUTION_FAILED",
            error_message="Job execution failed.",
        )
        failed = store.load(job_id)
        if attempts_remaining(attempt=failed.attempt, max_attempts=failed.max_attempts):
            _requeue_for_retry(
                store=store,
                queue=queue,
                infra=infra,
                job_id=job_id,
                attempt=failed.attempt,
            )
        else:
            _safe_ack(queue, job_id)
            log_operational_event("job_failed", job_id=job_id, worker_id=wid, retryable=True)
    finally:
        heartbeat.stop()


def register_worker_signals() -> None:
    """Register Celery worker lifecycle hooks."""
    app = get_celery_app()

    @app.on_after_finalize.connect  # type: ignore[untyped-decorator]
    def _register_shutdown_handler(**_: object) -> None:
        from celery.signals import worker_shutting_down

        @worker_shutting_down.connect  # type: ignore[untyped-decorator]
        def _on_shutdown(**__: object) -> None:
            request_worker_shutdown()


register_worker_signals()


@get_celery_app().task(name="ssri.execute_job", bind=True, max_retries=0)  # type: ignore[untyped-decorator]
def execute_job_task(self: object, job_id: str) -> None:
    _ = self
    execute_job_record(job_id)
