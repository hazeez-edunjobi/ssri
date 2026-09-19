"""Optional distributed infrastructure integration tests.

Enable with:
  SSRI_INTEGRATION_TESTS=1
  SSRI_DATABASE_URL=postgresql://ssri:ssri@localhost:5432/ssri
  SSRI_REDIS_URL=redis://localhost:6379/0

Start dependencies:
  docker compose -f model/docker-compose.yml up -d
"""

from __future__ import annotations

import os

import pytest

from ssri_model.infrastructure.config import ExecutionMode, InfrastructureConfig
from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.database.schema import create_database_engine, init_schema
from ssri_model.infrastructure.health import check_infrastructure_health
from ssri_model.infrastructure.redis.client import create_redis_client, ping_redis
from ssri_model.infrastructure.redis.queue import RedisJobQueue
from ssri_model.jobs.models import JobStatus, JobType
from ssri_model.jobs.service import utc_now_iso

pytestmark = pytest.mark.skipif(
    os.getenv("SSRI_INTEGRATION_TESTS", "").lower() not in {"1", "true", "yes"},
    reason="Set SSRI_INTEGRATION_TESTS=1 to run distributed integration tests",
)


@pytest.fixture(scope="module")
def infra_config() -> InfrastructureConfig:
    database_url = os.getenv("SSRI_DATABASE_URL")
    redis_url = os.getenv("SSRI_REDIS_URL")
    if not database_url or not redis_url:
        pytest.skip("SSRI_DATABASE_URL and SSRI_REDIS_URL required for integration tests")
    return InfrastructureConfig(
        execution_mode=ExecutionMode.DISTRIBUTED,
        database_url=database_url,
        redis_url=redis_url,
    )


@pytest.fixture(scope="module")
def job_store(infra_config: InfrastructureConfig) -> DatabaseJobStore:
    engine = create_database_engine(infra_config.database_url or "")
    init_schema(engine)
    store = DatabaseJobStore(engine, auto_init=False)
    yield store
    store.close()


@pytest.fixture(scope="module")
def job_queue(infra_config: InfrastructureConfig) -> RedisJobQueue:
    client = create_redis_client(infra_config.redis_url or "")
    if not ping_redis(client):
        pytest.skip("Redis unavailable")
    queue = RedisJobQueue(client)
    yield queue
    client.close()


def test_readiness_with_real_services(infra_config: InfrastructureConfig) -> None:
    health = check_infrastructure_health(infra_config)
    assert health.mode == "distributed"
    assert health.ready is True


def test_postgres_job_lifecycle(job_store: DatabaseJobStore, job_queue: RedisJobQueue) -> None:
    from ssri_model.jobs.models import JobRecord

    now = utc_now_iso()
    job_id = job_store.generate_job_id()
    record = JobRecord(
        job_id=job_id,
        request_id="integration-req",
        job_type=JobType.INFERENCE,
        status=JobStatus.QUEUED,
        created_at=now,
        queued_at=now,
        submitted_by_key_id="abc1234567890abcd",
        auth_role="operator",
        payload={"request_id": "integration-req"},
        max_attempts=3,
    )
    job_store.save(record)
    job_queue.enqueue(job_id)
    dequeued = job_queue.dequeue()
    assert dequeued == job_id
    claimed = job_store.claim(
        job_id,
        worker_id="integration-worker",
        started_at=utc_now_iso(),
        heartbeat_at=utc_now_iso(),
    )
    assert claimed is not None
    assert claimed.status == JobStatus.RUNNING
    job_store.transition(job_id, target=JobStatus.COMPLETED, expected=JobStatus.RUNNING)
    job_queue.acknowledge(job_id)
    final = job_store.load(job_id)
    assert final.status == JobStatus.COMPLETED
