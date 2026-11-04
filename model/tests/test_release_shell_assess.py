"""Assess behaviour with release shell flag."""

from __future__ import annotations

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from tests.api_helpers import build_api_config


def test_no_trained_model_when_release_shell_on(tmp_path, monkeypatch):
    monkeypatch.setenv("SSRI_RELEASE_SHELL", "true")
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post("/api/v1/assess", json={})
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "no_trained_model"
    assert "limitations" in body


def test_assess_still_requires_checkpoint_when_flag_off(tmp_path, monkeypatch):
    monkeypatch.delenv("SSRI_RELEASE_SHELL", raising=False)
    monkeypatch.delenv("SSRI_ASSESS_SOFTMAX", raising=False)
    client = TestClient(create_app(build_api_config(tmp_path)))
    response = client.post(
        "/api/v1/assess",
        json={"point": {"latitude": 6.52, "longitude": 3.38}},
    )
    assert response.status_code in {400, 422}
