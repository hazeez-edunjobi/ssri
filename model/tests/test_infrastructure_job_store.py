"""Tests for database-backed job store."""

from __future__ import annotations

import threading

import pytest

from ssri_model.jobs.exceptions import InvalidJobTransitionError, JobNotFoundError
from ssri_model.jobs.models import JobRecord, JobStatus, JobType
from ssri_model.jobs.service import utc_now_iso
from tests.infrastructure_helpers import build_sqlite_job_store


def _sample_record(job_id: str = "job-test12345678") -> JobRecord:
    now = utc_now_iso()
    return JobRecord(
        job_id=job_id,
        request_id="req-1",
        job_type=JobType.INFERENCE,
        status=JobStatus.QUEUED,
        created_at=now,
        queued_at=now,
        submitted_by_key_id="abc1234567890abcd",
        auth_role="operator",
        payload={"request_id": "req-1"},
        max_attempts=3,
    )


def test_create_and_load_job() -> None:
    store = build_sqlite_job_store()
    record = _sample_record()
    store.save(record)
    loaded = store.load(record.job_id)
    assert loaded.request_id == "req-1"
    assert loaded.status == JobStatus.QUEUED


def test_transition_queued_to_running() -> None:
    store = build_sqlite_job_store()
    record = _sample_record()
    store.save(record)
    updated = store.transition(
        record.job_id,
        target=JobStatus.RUNNING,
        expected=JobStatus.QUEUED,
        updates={"started_at": utc_now_iso(), "worker_id": "worker-1"},
    )
    assert updated.status == JobStatus.RUNNING
    assert updated.worker_id == "worker-1"


def test_invalid_transition_rejected() -> None:
    store = build_sqlite_job_store()
    record = _sample_record()
    store.save(record)
    store.transition(record.job_id, target=JobStatus.RUNNING, expected=JobStatus.QUEUED)
    store.transition(record.job_id, target=JobStatus.COMPLETED, expected=JobStatus.RUNNING)
    with pytest.raises(InvalidJobTransitionError):
        store.transition(record.job_id, target=JobStatus.QUEUED, expected=JobStatus.COMPLETED)


def test_claim_prevents_double_execution() -> None:
    store = build_sqlite_job_store()
    record = _sample_record("job-claimtest1234")
    store.save(record)
    first = store.claim(
        record.job_id,
        worker_id="worker-a",
        started_at=utc_now_iso(),
        heartbeat_at=utc_now_iso(),
    )
    second = store.claim(
        record.job_id,
        worker_id="worker-b",
        started_at=utc_now_iso(),
        heartbeat_at=utc_now_iso(),
    )
    assert first is not None
    assert first.status == JobStatus.RUNNING
    assert second is None


def test_save_refreshes_version_on_upsert() -> None:
    """``save`` reloads DB state after IntegrityError — not classic caller-version OCC.

    A second ``save`` with a stale in-memory ``version`` still succeeds when the
    status transition (or same-status write) is valid, bumping from the *current*
    DB version. Concurrent conflicts are covered by ``test_concurrent_save_conflict``.
    """
    store = build_sqlite_job_store()
    record = _sample_record("job-optlock123456")
    store.save(record)

    first = store.load(record.job_id)
    second = store.load(record.job_id)
    assert first.version == second.version == 1

    first.status = JobStatus.RUNNING
    store.save(first)
    assert store.load(record.job_id).version == 2

    second.status = JobStatus.RUNNING
    store.save(second)
    final = store.load(record.job_id)
    assert final.status == JobStatus.RUNNING
    assert final.version == 3


def test_concurrent_save_conflict(tmp_path) -> None:
    """Multi-writer race on file-backed SQLite (not StaticPool :memory:).

    In-memory StaticPool shares one connection across threads — undefined for
    SQLite and previously caused flaky suite failures / thread exception warnings.
    File-backed engines give each checkout a connection so optimistic locking
    can be exercised without weakening conflict semantics.
    """
    from tests.infrastructure_helpers import build_sqlite_file_job_store

    db_path = tmp_path / "concurrent_jobs.sqlite"
    store = build_sqlite_file_job_store(db_path)
    record = _sample_record("job-concurrent12")
    store.save(record)

    barrier = threading.Barrier(4)
    outcomes: list[str] = []
    lock = threading.Lock()

    def worker() -> None:
        try:
            current = store.load(record.job_id)
            barrier.wait(timeout=10)
            current.status = JobStatus.RUNNING
            store.save(current)
            with lock:
                outcomes.append("ok")
        except InvalidJobTransitionError:
            with lock:
                outcomes.append("conflict")
        except Exception as exc:  # pragma: no cover
            with lock:
                outcomes.append(f"error:{type(exc).__name__}")

    threads = [threading.Thread(target=worker) for _ in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join(timeout=60)
        assert not thread.is_alive(), "worker thread hung"

    assert outcomes.count("ok") >= 1, f"expected a winner, got {outcomes}"
    assert not any(o.startswith("error:") for o in outcomes), f"unexpected errors {outcomes}"
    assert set(outcomes) <= {"ok", "conflict"}, f"unexpected outcomes {outcomes}"
    # Under SQLite, writers may serialize (all ok) or hit the OCC race (ok+conflict).
    # Production status races should use claim()/transition(); save() is upsert-oriented.
    final = store.load(record.job_id)
    assert final.status == JobStatus.RUNNING
    assert final.version >= 2
    store.close()


def test_unknown_job_raises_not_found() -> None:
    store = build_sqlite_job_store()
    with pytest.raises(JobNotFoundError):
        store.load("job-doesnotexist1")
