"""Protocol definitions for replaceable job infrastructure."""

from __future__ import annotations

from collections.abc import Callable
from typing import Protocol, runtime_checkable

from ssri_model.jobs.models import JobRecord
from ssri_model.ratelimit import RateLimitResult


@runtime_checkable
class JobStoreProtocol(Protocol):
    """Persistent job record storage."""

    def save(self, record: JobRecord) -> None: ...

    def load(self, job_id: str) -> JobRecord: ...

    def save_result(self, job_id: str, result: dict[str, object]) -> None: ...

    def load_result(self, job_id: str) -> dict[str, object]: ...

    @staticmethod
    def generate_job_id() -> str: ...


@runtime_checkable
class IdempotencyStoreProtocol(Protocol):
    """Principal-scoped idempotency mapping."""

    def get(self, *, principal_key_id: str, idempotency_key: str) -> object | None: ...

    def put(
        self,
        *,
        principal_key_id: str,
        idempotency_key: str,
        job_id: str,
        request_fingerprint: str,
    ) -> object: ...


@runtime_checkable
class JobExecutorProtocol(Protocol):
    """Submit and manage background job execution."""

    def submit(self, job_id: str, worker: Callable[[], None] | None = None) -> None: ...

    def cancel(self, job_id: str) -> JobRecord: ...

    def get_status(self, job_id: str) -> JobRecord: ...

    @property
    def queued_count(self) -> int: ...

    def shutdown(self, *, wait: bool = False) -> None: ...


@runtime_checkable
class RateLimiterProtocol(Protocol):
    """Rate limiting keyed by client identifier."""

    def check(self, key: str, *, now: float | None = None) -> RateLimitResult: ...

    def reset(self, key: str | None = None) -> None: ...


@runtime_checkable
class JobQueueProtocol(Protocol):
    """Distributed work queue."""

    def enqueue(self, job_id: str) -> None: ...

    def acknowledge(self, job_id: str) -> None: ...

    def requeue(self, job_id: str) -> None: ...
