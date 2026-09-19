"""Tests for worker heartbeat maintenance."""

from __future__ import annotations

import time

from ssri_model.infrastructure.worker.heartbeat import HeartbeatController
from ssri_model.infrastructure.worker.lifecycle import (
    request_worker_shutdown,
    reset_worker_shutdown,
)
from ssri_model.jobs.models import JobRecord, JobStatus, JobType
from ssri_model.jobs.service import utc_now_iso
from tests.infrastructure_helpers import build_sqlite_job_store


def _running_job(*, job_id: str = "job-heartbeat1234") -> JobRecord:
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
        worker_id="worker-a",
        attempt=1,
        heartbeat_at=now,
        version=1,
    )


def test_update_heartbeat_refreshes_with_optimistic_lock() -> None:
    store = build_sqlite_job_store()
    record = _running_job()
    store.save(record)
    new_heartbeat = utc_now_iso()
    updated = store.update_heartbeat(
        record.job_id,
        worker_id="worker-a",
        heartbeat_at=new_heartbeat,
        expected_heartbeat_at=record.heartbeat_at,
        expected_version=record.version,
    )
    assert updated is True
    loaded = store.load(record.job_id)
    assert loaded.heartbeat_at == new_heartbeat
    assert loaded.version == 2


def test_stale_heartbeat_update_rejected() -> None:
    store = build_sqlite_job_store()
    record = _running_job()
    store.save(record)
    refreshed = utc_now_iso()
    store.update_heartbeat(
        record.job_id,
        worker_id="worker-a",
        heartbeat_at=refreshed,
        expected_heartbeat_at=record.heartbeat_at,
        expected_version=record.version,
    )
    stale_attempt = store.update_heartbeat(
        record.job_id,
        worker_id="worker-a",
        heartbeat_at=utc_now_iso(),
        expected_heartbeat_at=record.heartbeat_at,
        expected_version=record.version,
    )
    assert stale_attempt is False


def test_terminal_job_heartbeat_rejected() -> None:
    store = build_sqlite_job_store()
    record = _running_job()
    store.save(record)
    store.transition(record.job_id, target=JobStatus.COMPLETED, expected=JobStatus.RUNNING)
    updated = store.update_heartbeat(
        record.job_id,
        worker_id="worker-a",
        heartbeat_at=utc_now_iso(),
        expected_heartbeat_at=record.heartbeat_at,
        expected_version=record.version,
    )
    assert updated is False


def test_heartbeat_controller_periodic_refresh() -> None:
    store = build_sqlite_job_store()
    record = _running_job(job_id="job-hb-controller1")
    store.save(record)
    controller = HeartbeatController(
        store,
        job_id=record.job_id,
        worker_id="worker-a",
        interval_seconds=0.05,
    )
    controller.start(initial_heartbeat=record.heartbeat_at or utc_now_iso(), initial_version=1)
    time.sleep(0.15)
    controller.stop()
    loaded = store.load(record.job_id)
    assert loaded.heartbeat_at != record.heartbeat_at
    assert loaded.version > 1


def test_heartbeat_stops_on_worker_shutdown() -> None:
    store = build_sqlite_job_store()
    record = _running_job(job_id="job-hb-shutdown12")
    store.save(record)
    reset_worker_shutdown()
    controller = HeartbeatController(
        store,
        job_id=record.job_id,
        worker_id="worker-a",
        interval_seconds=0.05,
        should_continue=lambda: not __import__(
            "ssri_model.infrastructure.worker.lifecycle",
            fromlist=["worker_shutdown_requested"],
        ).worker_shutdown_requested(),
    )
    controller.start(initial_heartbeat=record.heartbeat_at or utc_now_iso(), initial_version=1)
    request_worker_shutdown()
    time.sleep(0.15)
    controller.stop()
    reset_worker_shutdown()
    loaded = store.load(record.job_id)
    assert loaded.status == JobStatus.RUNNING
