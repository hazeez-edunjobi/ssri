"""Tests for SSRI API health endpoints."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.config import APIConfig
from ssri_model.service.config import ServiceConfig
from tests.api_helpers import create_test_client


def test_root_health_returns_ok(tmp_path) -> None:
    client = create_test_client(tmp_path)
    response = client.get("/health")
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "ssri-inference"


def test_versioned_health_returns_ok(tmp_path) -> None:
    client = create_test_client(tmp_path)
    response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_returns_ready(tmp_path) -> None:
    client = create_test_client(tmp_path)
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_service_unavailable_when_output_root_not_usable(tmp_path) -> None:
    blocked = tmp_path / "blocked"
    blocked.write_text("not-a-directory", encoding="utf-8")
    service_config = ServiceConfig(output_root=str(blocked))
    config = APIConfig(service_config=service_config)
    client = TestClient(create_app(config))
    response = client.get("/api/v1/ready")
    assert response.status_code == 503
    payload = response.json()
    assert payload["error"]["code"] == "SERVICE_NOT_READY"
