"""Tests for distributed worker queue/database safety."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from ssri_model.infrastructure.worker.lifecycle import reset_worker_shutdown
from ssri_model.jobs.models import JobRecord, JobStatus, JobType
from ssri_model.jobs.service import utc_now_iso
from ssri_model.worker.tasks import execute_job_record
from tests.infrastructure_helpers import build_fakeredis_client, build_sqlite_job_store


def _queued_record(job_id: str = "job-worker-safe123") -> JobRecord:
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


def _build_context(store, queue, infra_config):
    api_config = MagicMock()
    api_config.infrastructure_config = infra_config
    api_config.service_config = MagicMock()
    job_service = MagicMock()
    return api_config, job_service, store, queue, infra_config


@patch("ssri_model.worker.tasks._build_worker_context")
def test_unknown_job_is_acknowledged_without_crash(mock_context: MagicMock) -> None:
    store = build_sqlite_job_store()
    from ssri_model.infrastructure.config import InfrastructureConfig
    from ssri_model.infrastructure.redis.queue import RedisJobQueue

    redis_client = build_fakeredis_client()
    queue = RedisJobQueue(redis_client)
    infra = InfrastructureConfig()
    mock_context.return_value = _build_context(store, queue, infra)
    execute_job_record("job-doesnotexist1")
    assert queue.depth() == 0


@patch("ssri_model.worker.tasks._build_worker_context")
def test_terminal_job_is_not_re_executed(mock_context: MagicMock) -> None:
    store = build_sqlite_job_store()
    from ssri_model.infrastructure.config import InfrastructureConfig
    from ssri_model.infrastructure.redis.queue import RedisJobQueue

    record = _queued_record("job-terminal123456")
    store.save(record)
    store.transition(record.job_id, target=JobStatus.RUNNING, expected=JobStatus.QUEUED)
    store.transition(record.job_id, target=JobStatus.COMPLETED, expected=JobStatus.RUNNING)
    redis_client = build_fakeredis_client()
    queue = RedisJobQueue(redis_client)
    infra = InfrastructureConfig()
    mock_context.return_value = _build_context(store, queue, infra)
    with patch("ssri_model.api.job_workers.run_inference_job") as mock_run:
        execute_job_record(record.job_id)
        mock_run.assert_not_called()


@patch("ssri_model.worker.tasks._build_worker_context")
def test_duplicate_claim_is_harmless(mock_context: MagicMock) -> None:
    store = build_sqlite_job_store()
    from ssri_model.infrastructure.config import InfrastructureConfig
    from ssri_model.infrastructure.redis.queue import RedisJobQueue

    record = _queued_record("job-duplicate12345")
    store.save(record)
    now = utc_now_iso()
    store.claim(record.job_id, worker_id="worker-first", started_at=now, heartbeat_at=now)
    redis_client = build_fakeredis_client()
    queue = RedisJobQueue(redis_client)
    infra = InfrastructureConfig()
    mock_context.return_value = _build_context(store, queue, infra)
    with patch("ssri_model.api.job_workers.run_inference_job") as mock_run:
        execute_job_record(record.job_id)
        mock_run.assert_not_called()


@patch("ssri_model.worker.tasks._build_worker_context")
def test_worker_shutdown_skips_new_work(mock_context: MagicMock) -> None:
    reset_worker_shutdown()
    from ssri_model.infrastructure.worker.lifecycle import request_worker_shutdown

    request_worker_shutdown()
    with patch("ssri_model.worker.tasks._build_worker_context") as mock_ctx:
        execute_job_record("job-any123456789")
        mock_ctx.assert_not_called()
    reset_worker_shutdown()
