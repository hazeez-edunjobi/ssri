"""Shared helpers for Stage 3.4 infrastructure tests."""

from __future__ import annotations

import fakeredis

from sqlalchemy.pool import StaticPool

from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.database.schema import create_database_engine, init_schema
from ssri_model.infrastructure.redis.idempotency import RedisIdempotencyStore
from ssri_model.infrastructure.redis.rate_limiter import RedisRateLimiter


def build_sqlite_job_store() -> DatabaseJobStore:
    engine = create_database_engine(
        "sqlite+pysqlite:///:memory:",
        poolclass=StaticPool,
        connect_args={"check_same_thread": False},
    )
    init_schema(engine)
    return DatabaseJobStore(engine, auto_init=False)


def build_sqlite_file_job_store(path) -> DatabaseJobStore:
    """File-backed SQLite suitable for multi-threaded optimistic-lock tests.

    Avoid StaticPool/:memory: here — a single shared connection is not safe for
    concurrent writers and previously caused flaky ``test_concurrent_save_conflict``.
    """
    from pathlib import Path

    db_path = Path(path)
    engine = create_database_engine(
        f"sqlite+pysqlite:///{db_path.as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    init_schema(engine)
    return DatabaseJobStore(engine, auto_init=False)


def build_fakeredis_client():
    return fakeredis.FakeRedis(decode_responses=True)


def build_redis_idempotency_store(*, ttl_seconds: int = 60) -> RedisIdempotencyStore:
    return RedisIdempotencyStore(build_fakeredis_client(), ttl_seconds=ttl_seconds)


def build_redis_rate_limiter(*, max_requests: int = 2, window_seconds: float = 10.0) -> RedisRateLimiter:
    return RedisRateLimiter(
        build_fakeredis_client(),
        max_requests=max_requests,
        window_seconds=window_seconds,
        bucket="test",
    )
