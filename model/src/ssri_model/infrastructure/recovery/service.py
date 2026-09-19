"""Stale worker lease recovery for durable jobs."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from ssri_model.infrastructure.config import InfrastructureConfig
from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.observability import log_operational_event
from ssri_model.infrastructure.redis.queue import RedisJobQueue
from ssri_model.jobs.models import JobStatus
from ssri_model.jobs.service import utc_now_iso
from ssri_model.worker.celery_app import get_celery_app


@dataclass(frozen=True)
class RecoveryResult:
    scanned: int
    recovered: int
    failed: int
    skipped: int


class LeaseRecoveryService:
    """Recover stale running jobs whose worker heartbeat exceeded the lease."""

    def __init__(
        self,
        store: DatabaseJobStore,
        config: InfrastructureConfig,
        *,
        queue: RedisJobQueue | None = None,
    ) -> None:
        self._store = store
        self._config = config
        self._queue = queue

    @property
    def config(self) -> InfrastructureConfig:
        return self._config

    def _heartbeat_cutoff(self, *, now: datetime | None = None) -> str:
        current = now or datetime.now(timezone.utc)
        cutoff = current - timedelta(seconds=self._config.job_lease_seconds)
        return cutoff.isoformat()

    def recover_once(self) -> RecoveryResult:
        if not self._config.lease_recovery_enabled:
            return RecoveryResult(scanned=0, recovered=0, failed=0, skipped=0)
        cutoff = self._heartbeat_cutoff()
        now = utc_now_iso()
        candidates = self._store.list_stale_running_jobs(
            heartbeat_cutoff=cutoff,
            limit=self._config.lease_recovery_batch_size,
        )
        recovered = 0
        failed = 0
        skipped = 0
        for candidate in candidates:
            updated = self._store.recover_stale_job(
                candidate.job_id,
                heartbeat_cutoff=cutoff,
                recovered_at=now,
            )
            if updated is None:
                skipped += 1
                continue
            if updated.status == JobStatus.QUEUED:
                recovered += 1
                if self._queue is not None:
                    self._queue.requeue(updated.job_id)
                get_celery_app().send_task(
                    self._config.celery_task_name,
                    args=[updated.job_id],
                )
                log_operational_event(
                    "job_recovered",
                    job_id=updated.job_id,
                    attempt=updated.attempt,
                    recovery_count=updated.recovery_count,
                )
            elif updated.status == JobStatus.FAILED:
                failed += 1
                if self._queue is not None:
                    self._queue.acknowledge(updated.job_id)
                log_operational_event(
                    "job_failed",
                    job_id=updated.job_id,
                    attempt=updated.attempt,
                    error_code=updated.error_code,
                    reason="lease_expired",
                )
        return RecoveryResult(
            scanned=len(candidates),
            recovered=recovered,
            failed=failed,
            skipped=skipped,
        )
