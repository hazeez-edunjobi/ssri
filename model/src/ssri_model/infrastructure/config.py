"""Infrastructure configuration for Stage 3.4 distributed execution."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping
from urllib.parse import urlparse

from ssri_model.service.exceptions import InvalidServiceConfigError


class ExecutionMode(str, Enum):
    LOCAL = "local"
    DISTRIBUTED = "distributed"


@dataclass(frozen=True)
class InfrastructureConfig:
    """Configuration for distributed job infrastructure."""

    execution_mode: ExecutionMode = ExecutionMode.LOCAL
    database_url: str | None = None
    redis_url: str | None = None
    celery_broker_url: str | None = None
    celery_result_backend: str | None = None
    max_attempts: int = 3
    retry_backoff_seconds: float = 5.0
    retry_backoff_max_seconds: float = 300.0
    retry_jitter_seconds: float = 1.0
    job_lease_seconds: int = 300
    worker_heartbeat_seconds: int = 30
    celery_task_name: str = "ssri.execute_job"
    lease_recovery_enabled: bool = False
    lease_recovery_interval_seconds: int = 60
    lease_recovery_batch_size: int = 50

    def __post_init__(self) -> None:
        if self.max_attempts < 1:
            raise InvalidServiceConfigError("max_attempts must be at least 1")
        if self.retry_backoff_seconds <= 0:
            raise InvalidServiceConfigError("retry_backoff_seconds must be positive")
        if self.retry_backoff_max_seconds <= 0:
            raise InvalidServiceConfigError("retry_backoff_max_seconds must be positive")
        if self.job_lease_seconds <= 0:
            raise InvalidServiceConfigError("job_lease_seconds must be positive")
        if self.worker_heartbeat_seconds <= 0:
            raise InvalidServiceConfigError("worker_heartbeat_seconds must be positive")
        if self.worker_heartbeat_seconds >= self.job_lease_seconds:
            raise InvalidServiceConfigError(
                "worker_heartbeat_seconds must be shorter than job_lease_seconds"
            )
        if self.lease_recovery_interval_seconds <= 0:
            raise InvalidServiceConfigError("lease_recovery_interval_seconds must be positive")
        if self.lease_recovery_batch_size < 1:
            raise InvalidServiceConfigError("lease_recovery_batch_size must be at least 1")
        if self.execution_mode == ExecutionMode.DISTRIBUTED:
            if not self.database_url:
                raise InvalidServiceConfigError(
                    "database_url is required when execution_mode=distributed"
                )
            if not self.redis_url:
                raise InvalidServiceConfigError(
                    "redis_url is required when execution_mode=distributed"
                )
            _validate_database_url(self.database_url)
            _validate_redis_url(self.redis_url)

    @property
    def is_distributed(self) -> bool:
        return self.execution_mode == ExecutionMode.DISTRIBUTED

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["execution_mode"] = self.execution_mode.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> InfrastructureConfig:
        mode_raw = str(payload.get("execution_mode", ExecutionMode.LOCAL.value)).lower()
        return cls(
            execution_mode=ExecutionMode(mode_raw),
            database_url=_optional_str(payload.get("database_url")),
            redis_url=_optional_str(payload.get("redis_url")),
            celery_broker_url=_optional_str(payload.get("celery_broker_url")),
            celery_result_backend=_optional_str(payload.get("celery_result_backend")),
            max_attempts=int(payload.get("max_attempts", 3)),
            retry_backoff_seconds=float(payload.get("retry_backoff_seconds", 5.0)),
            retry_backoff_max_seconds=float(payload.get("retry_backoff_max_seconds", 300.0)),
            retry_jitter_seconds=float(payload.get("retry_jitter_seconds", 1.0)),
            job_lease_seconds=int(payload.get("job_lease_seconds", 300)),
            worker_heartbeat_seconds=int(payload.get("worker_heartbeat_seconds", 30)),
            celery_task_name=str(payload.get("celery_task_name", "ssri.execute_job")),
            lease_recovery_enabled=bool(payload.get("lease_recovery_enabled", False)),
            lease_recovery_interval_seconds=int(
                payload.get("lease_recovery_interval_seconds", 60)
            ),
            lease_recovery_batch_size=int(payload.get("lease_recovery_batch_size", 50)),
        )

    @classmethod
    def from_env(cls, *, prefix: str = "SSRI_") -> InfrastructureConfig:
        mode_raw = os.getenv(f"{prefix}EXECUTION_MODE", ExecutionMode.LOCAL.value).lower()
        redis_url = os.getenv(f"{prefix}REDIS_URL")
        return cls(
            execution_mode=ExecutionMode(mode_raw),
            database_url=os.getenv(f"{prefix}DATABASE_URL"),
            redis_url=redis_url,
            celery_broker_url=os.getenv(f"{prefix}CELERY_BROKER_URL", redis_url),
            celery_result_backend=os.getenv(f"{prefix}CELERY_RESULT_BACKEND", redis_url),
            max_attempts=int(os.getenv(f"{prefix}MAX_ATTEMPTS", "3")),
            retry_backoff_seconds=float(os.getenv(f"{prefix}RETRY_BACKOFF_SECONDS", "5")),
            retry_backoff_max_seconds=float(
                os.getenv(f"{prefix}RETRY_BACKOFF_MAX_SECONDS", "300")
            ),
            retry_jitter_seconds=float(os.getenv(f"{prefix}RETRY_JITTER_SECONDS", "1")),
            job_lease_seconds=int(os.getenv(f"{prefix}JOB_LEASE_SECONDS", "300")),
            worker_heartbeat_seconds=int(os.getenv(f"{prefix}WORKER_HEARTBEAT_SECONDS", "30")),
            lease_recovery_enabled=os.getenv(f"{prefix}LEASE_RECOVERY_ENABLED", "false").lower()
            in {"1", "true", "yes"},
            lease_recovery_interval_seconds=int(
                os.getenv(f"{prefix}LEASE_RECOVERY_INTERVAL_SECONDS", "60")
            ),
            lease_recovery_batch_size=int(
                os.getenv(f"{prefix}LEASE_RECOVERY_BATCH_SIZE", "50")
            ),
        )


def _optional_str(value: object | None) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    return normalized or None


def _validate_database_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"postgresql", "postgresql+psycopg", "sqlite", "sqlite+pysqlite"}:
        raise InvalidServiceConfigError("database_url must use a supported scheme")


def _validate_redis_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"redis", "rediss", "unix"}:
        raise InvalidServiceConfigError("redis_url must use redis:// or rediss://")
