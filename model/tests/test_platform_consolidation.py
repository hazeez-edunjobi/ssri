"""Platform consolidation / Compose configuration smoke tests."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_FILE = REPO_ROOT / "infra" / "docker-compose.yml"
MODEL_DOCKERFILE = REPO_ROOT / "model" / "Dockerfile"
ENTRYPOINT = REPO_ROOT / "model" / "docker-entrypoint.sh"


def test_model_dockerfile_exists() -> None:
    assert MODEL_DOCKERFILE.is_file()
    text = MODEL_DOCKERFILE.read_text(encoding="utf-8")
    assert "ssri_model" in text or "PYTHONPATH" in text
    assert ENTRYPOINT.is_file()


def test_compose_file_targets_model_package() -> None:
    text = COMPOSE_FILE.read_text(encoding="utf-8")
    assert "context: ../model" in text
    assert "ssri_model.worker.celery_app" in text or 'command: ["worker"]' in text
    assert "SSRI_EXECUTION_MODE" in text
    assert "SSRI_DATABASE_URL" in text
    assert "SSRI_REDIS_URL" in text
    # Must not build obsolete Stage-0 api/ package
    assert "context: ../api" not in text
    assert "context: ../worker" not in text


def test_docker_compose_config_validates() -> None:
    result = subprocess.run(
        ["docker", "compose", "-f", str(COMPOSE_FILE), "config"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0 and "env file" in (result.stderr + result.stdout).lower():
        pytest.skip("Compose requires a local .env; create from .env.example")
    assert result.returncode == 0, result.stderr or result.stdout
    assert "ssri-api" in result.stdout or "api:" in result.stdout


def test_create_app_loads_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_API_SERVICE_NAME", "ssri-compose-smoke")
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    from ssri_model.api.app import create_app

    app = create_app()
    assert app.state.ssri.api_config.service_name == "ssri-compose-smoke"
    assert app.state.ssri.api_config.infrastructure_config.execution_mode.value == "local"
