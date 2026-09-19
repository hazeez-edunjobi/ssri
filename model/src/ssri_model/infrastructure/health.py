"""Infrastructure health checks."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from sqlalchemy import text

from ssri_model.infrastructure.config import ExecutionMode, InfrastructureConfig
from ssri_model.infrastructure.database.schema import create_database_engine, schema_initialized
from ssri_model.infrastructure.observability import log_operational_event
from ssri_model.infrastructure.redis.client import create_redis_client, ping_redis
from ssri_model.infrastructure.redis.queue import RedisJobQueue


@dataclass(frozen=True)
class ComponentHealth:
    name: str
    status: str
    detail: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


@dataclass(frozen=True)
class InfrastructureHealth:
    mode: str
    ready: bool
    components: tuple[ComponentHealth, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "ready": self.ready,
            "components": [component.to_dict() for component in self.components],
        }


def _config_consistent(config: InfrastructureConfig) -> tuple[bool, str]:
    if config.worker_heartbeat_seconds >= config.job_lease_seconds:
        return False, "heartbeat_interval_not_shorter_than_lease"
    if config.max_attempts < 1:
        return False, "invalid_max_attempts"
    return True, "ok"


def check_infrastructure_health(config: InfrastructureConfig) -> InfrastructureHealth:
    components: list[ComponentHealth] = []
    if config.execution_mode == ExecutionMode.LOCAL:
        components.append(ComponentHealth(name="execution", status="ok", detail="local"))
        return InfrastructureHealth(
            mode=config.execution_mode.value,
            ready=True,
            components=tuple(components),
        )

    config_ok, config_detail = _config_consistent(config)
    components.append(
        ComponentHealth(
            name="configuration",
            status="ok" if config_ok else "unavailable",
            detail=config_detail,
        )
    )

    db_ok = False
    db_detail = "unconfigured"
    if config.database_url:
        try:
            engine = create_database_engine(config.database_url)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            db_ok = schema_initialized(engine)
            db_detail = "connected" if db_ok else "schema_missing"
            engine.dispose()
        except Exception as exc:
            db_detail = f"unavailable: {type(exc).__name__}"
    components.append(
        ComponentHealth(
            name="postgresql",
            status="ok" if db_ok else "unavailable",
            detail=db_detail,
        )
    )

    redis_ok = False
    redis_detail = "unconfigured"
    queue_ok = False
    queue_detail = "unconfigured"
    if config.redis_url:
        try:
            client = create_redis_client(config.redis_url)
            redis_ok = ping_redis(client)
            redis_detail = "connected" if redis_ok else "ping_failed"
            if redis_ok:
                queue = RedisJobQueue(client)
                _ = queue.depth()
                queue_ok = True
                queue_detail = "reachable"
            client.close()
        except Exception as exc:
            redis_detail = f"unavailable: {type(exc).__name__}"
            queue_detail = f"unavailable: {type(exc).__name__}"
    components.append(
        ComponentHealth(
            name="redis",
            status="ok" if redis_ok else "unavailable",
            detail=redis_detail,
        )
    )
    components.append(
        ComponentHealth(
            name="queue",
            status="ok" if queue_ok else "unavailable",
            detail=queue_detail,
        )
    )

    ready = config_ok and db_ok and redis_ok and queue_ok
    if not ready:
        log_operational_event("infrastructure_unavailable", mode=config.execution_mode.value)
    return InfrastructureHealth(
        mode=config.execution_mode.value,
        ready=ready,
        components=tuple(components),
    )
