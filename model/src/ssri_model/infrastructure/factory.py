"""Build infrastructure components from configuration."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ssri_model.api.config import APIConfig
from ssri_model.infrastructure.config import ExecutionMode
from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.database.schema import create_database_engine
from ssri_model.infrastructure.executor.distributed import DistributedJobExecutor
from ssri_model.infrastructure.redis.client import create_redis_client
from ssri_model.infrastructure.redis.idempotency import RedisIdempotencyStore
from ssri_model.infrastructure.redis.queue import RedisJobQueue
from ssri_model.infrastructure.redis.rate_limiter import RedisRateLimiter
from ssri_model.jobs.executor import LocalJobExecutor
from ssri_model.jobs.idempotency import FileIdempotencyStore
from ssri_model.jobs.service import JobService
from ssri_model.jobs.store import FileJobStore
from ssri_model.ratelimit import RateLimiter
from ssri_model.service.validation import resolve_under_output_root


@dataclass
class InfrastructureResources:
    job_store: Any
    idempotency_store: Any
    job_executor: Any
    job_service: JobService
    inference_rate_limiter: Any
    batch_rate_limiter: Any
    status_rate_limiter: Any
    database_engine: Any | None = None
    redis_client: Any | None = None

    def shutdown(self, *, wait: bool = False) -> None:
        if hasattr(self.job_executor, "shutdown"):
            self.job_executor.shutdown(wait=wait)
        if self.database_engine is not None:
            self.database_engine.dispose()
        if self.redis_client is not None:
            self.redis_client.close()


def _build_rate_limiters(
    *,
    operational: Any,
    redis_client: Any | None,
) -> tuple[Any, Any, Any]:
    if redis_client is not None and operational.rate_limit_enabled:
        return (
            RedisRateLimiter(
                redis_client,
                max_requests=operational.inference_requests_per_window,
                window_seconds=operational.inference_window_seconds,
                bucket="inference",
            ),
            RedisRateLimiter(
                redis_client,
                max_requests=operational.batch_requests_per_window,
                window_seconds=operational.batch_window_seconds,
                bucket="batch",
            ),
            RedisRateLimiter(
                redis_client,
                max_requests=operational.status_requests_per_window,
                window_seconds=operational.status_window_seconds,
                bucket="status",
            ),
        )
    return (
        RateLimiter(
            max_requests=operational.inference_requests_per_window,
            window_seconds=operational.inference_window_seconds,
        ),
        RateLimiter(
            max_requests=operational.batch_requests_per_window,
            window_seconds=operational.batch_window_seconds,
        ),
        RateLimiter(
            max_requests=operational.status_requests_per_window,
            window_seconds=operational.status_window_seconds,
        ),
    )


def _build_distributed(api_config: APIConfig) -> InfrastructureResources:
    operational = api_config.operational_config
    infra = api_config.infrastructure_config
    assert infra.database_url is not None
    assert infra.redis_url is not None
    engine = create_database_engine(infra.database_url)
    redis_client = create_redis_client(infra.redis_url)
    job_store = DatabaseJobStore(engine)
    idempotency_store = RedisIdempotencyStore(
        redis_client,
        ttl_seconds=operational.idempotency_ttl_seconds,
    )
    queue = RedisJobQueue(redis_client)
    job_executor = DistributedJobExecutor(
        job_store,
        queue,
        max_queue_size=operational.max_queue_size,
        celery_task_name=infra.celery_task_name,
    )
    inference_rate_limiter, batch_rate_limiter, status_rate_limiter = _build_rate_limiters(
        operational=operational,
        redis_client=redis_client,
    )
    job_service = JobService(
        job_store,
        job_executor,
        idempotency_store,
        async_enabled=operational.async_enabled,
        max_attempts=infra.max_attempts,
    )
    return InfrastructureResources(
        job_store=job_store,
        idempotency_store=idempotency_store,
        job_executor=job_executor,
        job_service=job_service,
        inference_rate_limiter=inference_rate_limiter,
        batch_rate_limiter=batch_rate_limiter,
        status_rate_limiter=status_rate_limiter,
        database_engine=engine,
        redis_client=redis_client,
    )


def _build_local(api_config: APIConfig) -> InfrastructureResources:
    operational = api_config.operational_config
    infra = api_config.infrastructure_config
    job_root = resolve_under_output_root(
        api_config.output_root,
        operational.job_store_root,
    )
    job_store = FileJobStore(job_root)
    idempotency_store = FileIdempotencyStore(job_root / "idempotency")
    job_executor = LocalJobExecutor(
        job_store,
        max_workers=operational.worker_count,
        max_queue_size=operational.max_queue_size,
    )
    inference_rate_limiter, batch_rate_limiter, status_rate_limiter = _build_rate_limiters(
        operational=operational,
        redis_client=None,
    )
    job_service = JobService(
        job_store,
        job_executor,
        idempotency_store,
        async_enabled=operational.async_enabled,
        max_attempts=infra.max_attempts,
    )
    return InfrastructureResources(
        job_store=job_store,
        idempotency_store=idempotency_store,
        job_executor=job_executor,
        job_service=job_service,
        inference_rate_limiter=inference_rate_limiter,
        batch_rate_limiter=batch_rate_limiter,
        status_rate_limiter=status_rate_limiter,
    )


def build_infrastructure(api_config: APIConfig) -> InfrastructureResources:
    if api_config.infrastructure_config.execution_mode == ExecutionMode.DISTRIBUTED:
        return _build_distributed(api_config)
    return _build_local(api_config)
