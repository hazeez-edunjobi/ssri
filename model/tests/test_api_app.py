"""Tests for SSRI API application factory."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from tests.api_helpers import build_api_config


def test_create_app_exposes_openapi(tmp_path) -> None:
    app = create_app(build_api_config(tmp_path))
    client = TestClient(app)
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "SSRI Model API" in response.json()["info"]["title"]


def test_create_app_can_disable_docs(tmp_path) -> None:
    config = build_api_config(tmp_path, docs_enabled=False)
    client = TestClient(create_app(config))
    assert client.get("/docs").status_code == 404
