"""Tests for stale lease recovery."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

from ssri_model.infrastructure.config import InfrastructureConfig
from ssri_model.infrastructure.recovery.service import LeaseRecoveryService
from ssri_model.jobs.models import JobRecord, JobStatus, JobType
from ssri_model.jobs.service import utc_now_iso
from tests.infrastructure_helpers import build_sqlite_job_store


def _running_record(
    *,
    job_id: str = "job-recovery12345",
    attempt: int = 1,
    max_attempts: int = 3,
    heartbeat_at: str,
) -> JobRecord:
    now = utc_now_iso()
    return JobRecord(
        job_id=job_id,
        request_id="req-1",
        job_type=JobType.INFERENCE,
        status=JobStatus.RUNNING,
        created_at=now,
        queued_at=now,
        started_at=now,
        submitted_by_key_id="abc1234567890abcd",
        auth_role="operator",
        payload={"request_id": "req-1"},
        worker_id="worker-stale",
        attempt=attempt,
        max_attempts=max_attempts,
        heartbeat_at=heartbeat_at,
    )


def _stale_heartbeat(*, lease_seconds: int = 300) -> str:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=lease_seconds + 10)
    return cutoff.isoformat()


def test_recover_stale_job_requeues_when_attempts_remain() -> None:
    store = build_sqlite_job_store()
    stale = _stale_heartbeat()
    record = _running_record(attempt=1, max_attempts=3, heartbeat_at=stale)
    store.save(record)
    cutoff = datetime.now(timezone.utc).isoformat()
    updated = store.recover_stale_job(
        record.job_id,
        heartbeat_cutoff=cutoff,
        recovered_at=utc_now_iso(),
    )
    assert updated is not None
    assert updated.status == JobStatus.QUEUED
    assert updated.worker_id is None
    assert updated.heartbeat_at is None
    assert updated.recovery_count == 1
    assert updated.error_code == "STALE_LEASE_RECOVERED"


def test_recover_stale_job_fails_when_attempts_exhausted() -> None:
    store = build_sqlite_job_store()
    stale = _stale_heartbeat()
    record = _running_record(attempt=3, max_attempts=3, heartbeat_at=stale)
    store.save(record)
    cutoff = datetime.now(timezone.utc).isoformat()
    updated = store.recover_stale_job(
        record.job_id,
        heartbeat_cutoff=cutoff,
        recovered_at=utc_now_iso(),
    )
    assert updated is not None
    assert updated.status == JobStatus.FAILED
    assert updated.error_code == "LEASE_EXPIRED"


def test_recover_stale_job_skips_fresh_heartbeat() -> None:
    store = build_sqlite_job_store()
    fresh = utc_now_iso()
    record = _running_record(heartbeat_at=fresh)
    store.save(record)
    cutoff = _stale_heartbeat()
    updated = store.recover_stale_job(
        record.job_id,
        heartbeat_cutoff=cutoff,
        recovered_at=utc_now_iso(),
    )
    assert updated is None


def test_recover_stale_job_idempotent_for_terminal_job() -> None:
    store = build_sqlite_job_store()
    stale = _stale_heartbeat()
    record = _running_record(heartbeat_at=stale)
    store.save(record)
    store.transition(record.job_id, target=JobStatus.COMPLETED, expected=JobStatus.RUNNING)
    cutoff = datetime.now(timezone.utc).isoformat()
    updated = store.recover_stale_job(
        record.job_id,
        heartbeat_cutoff=cutoff,
        recovered_at=utc_now_iso(),
    )
    assert updated is None


def test_concurrent_recovery_only_one_succeeds() -> None:
    store = build_sqlite_job_store()
    stale = _stale_heartbeat()
    record = _running_record(job_id="job-concurrent-rec1", heartbeat_at=stale)
    store.save(record)
    cutoff = datetime.now(timezone.utc).isoformat()
    now = utc_now_iso()
    first = store.recover_stale_job(record.job_id, heartbeat_cutoff=cutoff, recovered_at=now)
    second = store.recover_stale_job(record.job_id, heartbeat_cutoff=cutoff, recovered_at=now)
    assert first is not None
    assert first.status == JobStatus.QUEUED
    assert second is None


def test_lease_recovery_service_disabled_by_default() -> None:
    store = build_sqlite_job_store()
    config = InfrastructureConfig(lease_recovery_enabled=False)
    service = LeaseRecoveryService(store, config)
    result = service.recover_once()
    assert result.scanned == 0
    assert result.recovered == 0


@patch("ssri_model.infrastructure.recovery.service.get_celery_app")
def test_lease_recovery_service_requeues_and_enqueues(mock_celery: MagicMock) -> None:
    store = build_sqlite_job_store()
    stale = _stale_heartbeat()
    record = _running_record(job_id="job-sweep1234567", heartbeat_at=stale)
    store.save(record)
    queue = MagicMock()
    config = InfrastructureConfig(
        lease_recovery_enabled=True,
        job_lease_seconds=300,
        lease_recovery_batch_size=10,
    )
    service = LeaseRecoveryService(store, config, queue=queue)
    result = service.recover_once()
    assert result.scanned == 1
    assert result.recovered == 1
    queue.requeue.assert_called_once_with(record.job_id)
    mock_celery.return_value.send_task.assert_called_once()
