"""SQLAlchemy schema for durable job storage."""

from __future__ import annotations

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    Index,
    Integer,
    MetaData,
    String,
    Table,
    Text,
    create_engine,
    inspect,
)
from sqlalchemy.engine import Engine

metadata = MetaData()

jobs_table = Table(
    "ssri_jobs",
    metadata,
    Column("job_id", String(128), primary_key=True),
    Column("request_id", String(128), nullable=False),
    Column("job_type", String(32), nullable=False),
    Column("status", String(32), nullable=False),
    Column("submitted_by_key_id", String(128), nullable=False),
    Column("auth_role", String(32), nullable=False),
    Column("scientific_validation_status", String(64), nullable=False),
    Column("idempotency_key", String(128), nullable=True),
    Column("payload", JSON, nullable=False),
    Column("result", JSON, nullable=True),
    Column("created_at", String(64), nullable=False),
    Column("queued_at", String(64), nullable=True),
    Column("started_at", String(64), nullable=True),
    Column("completed_at", String(64), nullable=True),
    Column("failed_at", String(64), nullable=True),
    Column("cancel_requested", Boolean, nullable=False, default=False),
    Column("error_code", String(64), nullable=True),
    Column("error_message", Text, nullable=True),
    Column("output_dir", Text, nullable=True),
    Column("output_location", Text, nullable=True),
    Column("worker_id", String(128), nullable=True),
    Column("attempt", Integer, nullable=False, default=0),
    Column("max_attempts", Integer, nullable=False, default=3),
    Column("heartbeat_at", String(64), nullable=True),
    Column("version", Integer, nullable=False, default=1),
    Column("recovery_count", Integer, nullable=False, default=0),
    Column("last_recovery_at", String(64), nullable=True),
    Index("ix_ssri_jobs_status", "status"),
    Index("ix_ssri_jobs_heartbeat_at", "heartbeat_at"),
    Index("ix_ssri_jobs_submitted_by_key_id", "submitted_by_key_id"),
    Index("ix_ssri_jobs_created_at", "created_at"),
)


def create_database_engine(database_url: str, **kwargs: object) -> Engine:
    return create_engine(database_url, pool_pre_ping=True, future=True, **kwargs)


def init_schema(engine: Engine) -> None:
    metadata.create_all(engine)


def schema_initialized(engine: Engine) -> bool:
    inspector = inspect(engine)
    return inspector.has_table("ssri_jobs")
