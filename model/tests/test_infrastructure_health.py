"""Tests for infrastructure health reporting."""

from __future__ import annotations

import pytest

from ssri_model.infrastructure.config import ExecutionMode, InfrastructureConfig
from ssri_model.infrastructure.health import check_infrastructure_health
from ssri_model.service.exceptions import InvalidServiceConfigError


def test_local_mode_ready_without_external_services() -> None:
    health = check_infrastructure_health(InfrastructureConfig(execution_mode=ExecutionMode.LOCAL))
    assert health.ready is True
    assert health.mode == "local"


def test_distributed_mode_unready_without_urls() -> None:
    config = InfrastructureConfig(
        execution_mode=ExecutionMode.DISTRIBUTED,
        database_url="postgresql://user:pass@localhost:5432/ssri",
        redis_url="redis://localhost:6379/0",
    )
    health = check_infrastructure_health(config)
    assert health.ready is False
    names = {component.name for component in health.components}
    assert "postgresql" in names
    assert "redis" in names
    assert "queue" in names
    assert "configuration" in names


def test_distributed_mode_reports_invalid_config() -> None:
    with pytest.raises(InvalidServiceConfigError):
        InfrastructureConfig(
            execution_mode=ExecutionMode.DISTRIBUTED,
            database_url="postgresql://user:pass@localhost:5432/ssri",
            redis_url="redis://localhost:6379/0",
            worker_heartbeat_seconds=400,
            job_lease_seconds=300,
        )
