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
    body = response.json()
    assert body["status"] == "ready"
    assert body.get("demo_mode") is False
    registry = body.get("model_registry") or {}
    assert registry.get("active_model_id") is None
    assert registry.get("checkpoint_available") is False


def test_ready_reports_demo_mode_when_enabled(tmp_path) -> None:
    from tests.api_helpers import build_api_config

    client = TestClient(create_app(build_api_config(tmp_path, demo_mode=True)))
    response = client.get("/api/v1/ready")
    assert response.status_code == 200
    assert response.json()["demo_mode"] is True


def test_ready_reports_promoted_registry_without_paths(tmp_path) -> None:
    import json

    from ssri_model.manual_training.storage import TrainingStorage
    from tests.api_helpers import build_api_config
    from tests.inference_helpers import save_inference_checkpoint

    output_root = tmp_path / "service-outputs"
    storage = TrainingStorage(str(output_root))
    model_id = "model-ready"
    dest = storage.models_dir / model_id
    dest.mkdir(parents=True)
    ckpt = dest / "best.pt"
    save_inference_checkpoint(ckpt)
    (storage.models_dir / "registry.json").write_text(
        json.dumps(
            {
                "models": [
                    {
                        "model_id": model_id,
                        "name": "Ready probe",
                        "created_at": "2026-01-01T00:00:00+00:00",
                        "dataset_id": "ds",
                        "dataset_name": "registry-fixture",
                        "checkpoint_path": str(ckpt.resolve()),
                        "experiment_dir": str(dest.resolve()),
                        "job_id": None,
                        "training_metrics": {},
                        "evaluation_status": "training_metrics_only",
                        "scientific_validation_status": "NOT_VALIDATED",
                        "active": False,
                        "notes": "",
                    }
                ]
            }
        ),
        encoding="utf-8",
    )
    (storage.models_dir / "active.json").write_text(
        json.dumps(
            {
                "model_id": model_id,
                "checkpoint_path": str(ckpt.resolve()),
                "activated_at": "2026-01-01T00:00:00+00:00",
            }
        ),
        encoding="utf-8",
    )
    client = TestClient(create_app(build_api_config(tmp_path)))
    body = client.get("/api/v1/ready").json()
    registry = body["model_registry"]
    assert registry["active_model_id"] == model_id
    assert registry["checkpoint_available"] is True
    assert "checkpoint_path" not in registry
    assert str(ckpt) not in json.dumps(body)


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
