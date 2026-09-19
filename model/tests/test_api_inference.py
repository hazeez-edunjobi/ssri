"""Tests for SSRI API inference endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.dependencies import create_app_state
from ssri_model.service.config import ServiceConfig
from tests.api_helpers import (
    FailingInferenceExecutor,
    build_api_config,
    build_inference_fixture,
    build_inference_payload,
    create_test_client,
)
from tests.orchestration_helpers import failing_run_inference


def test_inference_success(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = build_inference_payload(
        request_id="req-001",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["request_id"] == "req-001"
    assert body["status"] == "completed"
    assert body["scientific_validation_status"] == "NOT_VALIDATED"
    assert body["provenance"]["request_id"] == "req-001"
    assert body["prediction_path"] is not None


def test_inference_malformed_payload_returns_422(tmp_path: Path) -> None:
    client = create_test_client(tmp_path)
    response = client.post("/api/v1/inference", json={"request_id": "only-id"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "VALIDATION_ERROR"


def test_inference_missing_checkpoint_returns_400(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = build_inference_payload(
        request_id="req-missing",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=tmp_path / "missing.pt",
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_inference_unsafe_request_id_rejected(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = build_inference_payload(
        request_id="../evil",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PATH_SAFETY_VIOLATION"


def test_inference_path_traversal_in_output_dir_rejected(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = build_inference_payload(
        request_id="req-safe",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
        output_dir="../outside",
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PATH_SAFETY_VIOLATION"


def test_inference_scientific_gate_rejection_returns_403(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    config = build_api_config(
        tmp_path,
        service_config=ServiceConfig(
            output_root=str(tmp_path / "service-outputs"),
            scientific_validation_required=True,
        ),
    )
    client = create_test_client(tmp_path, api_config=config)
    payload = build_inference_payload(
        request_id="req-gate",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
        scientific_validation_status="NOT_VALIDATED",
        scientific_validation_required=True,
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SCIENTIFIC_GATE_REJECTED"


def test_inference_preserves_scientific_status(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = build_inference_payload(
        request_id="req-status",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
        scientific_validation_status="DATASET_AUDITED",
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["scientific_validation_status"] == "DATASET_AUDITED"
    assert body["provenance"]["scientific_validation_status"] == "DATASET_AUDITED"


def test_inference_metadata_endpoint(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = build_inference_payload(
        request_id="req-meta",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    create_response = client.post("/api/v1/inference", json=payload)
    assert create_response.status_code == 200

    metadata_response = client.get("/api/v1/inference/req-meta")
    assert metadata_response.status_code == 200
    metadata = metadata_response.json()
    assert metadata["request_id"] == "req-meta"
    assert metadata["provenance"]["request_id"] == "req-meta"


def test_inference_metadata_not_found(tmp_path: Path) -> None:
    client = create_test_client(tmp_path)
    response = client.get("/api/v1/inference/missing-id")
    assert response.status_code == 404


def test_inference_internal_exception_sanitized(tmp_path: Path) -> None:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    config = build_api_config(tmp_path)
    app = create_app(config, inference_runner=failing_run_inference)
    state = create_app_state(config, inference_executor=FailingInferenceExecutor(config.service_config))
    app.state.ssri = state
    client = TestClient(app, raise_server_exceptions=False)
    payload = build_inference_payload(
        request_id="req-fail",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 500
    message = response.json()["error"]["message"]
    assert "C:\\" not in message
    assert "/etc/" not in message
