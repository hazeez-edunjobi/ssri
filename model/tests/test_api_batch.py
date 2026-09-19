"""Tests for SSRI API batch endpoints."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from ssri_model.api.app import create_app
from ssri_model.api.dependencies import create_app_state
from tests.api_helpers import (
    FailingBatchExecutor,
    build_api_config,
    build_batch_fixture,
    create_test_client,
)
from tests.orchestration_helpers import failing_run_inference


def test_batch_success(tmp_path: Path) -> None:
    jobs_file, output_root, batch_id = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    client = create_test_client(tmp_path)
    payload = {
        "request_id": "batch-req-1",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
        "resume": False,
        "scientific_validation_status": "NOT_VALIDATED",
    }
    response = client.post("/api/v1/batch", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["batch_id"] == batch_id
    assert body["status"] in {"completed", "completed_with_errors"}
    assert body["completed_jobs"] >= 1


def test_batch_invalid_request_returns_400(tmp_path: Path) -> None:
    client = create_test_client(tmp_path)
    payload = {
        "request_id": "batch-req-2",
        "jobs_file": str(tmp_path / "missing.json"),
        "output_root": str(tmp_path / "service-outputs" / "batches" / "missing"),
    }
    response = client.post("/api/v1/batch", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "INVALID_REQUEST"


def test_batch_unsafe_request_id_rejected(tmp_path: Path) -> None:
    jobs_file, output_root, _ = build_batch_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = {
        "request_id": "../../bad",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    response = client.post("/api/v1/batch", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PATH_SAFETY_VIOLATION"


def test_batch_path_traversal_output_root_rejected(tmp_path: Path) -> None:
    jobs_file, _, _ = build_batch_fixture(tmp_path)
    client = create_test_client(tmp_path)
    payload = {
        "request_id": "batch-safe",
        "jobs_file": str(jobs_file),
        "output_root": "../escape",
    }
    response = client.post("/api/v1/batch", json=payload)
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PATH_SAFETY_VIOLATION"


def test_batch_status_endpoint(tmp_path: Path) -> None:
    jobs_file, output_root, batch_id = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    client = create_test_client(tmp_path)
    create_payload = {
        "request_id": "batch-req-status",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    assert client.post("/api/v1/batch", json=create_payload).status_code == 200

    status_response = client.get(
        f"/api/v1/batch/{batch_id}/status",
        params={"output_root": str(output_root)},
    )
    assert status_response.status_code == 200
    body = status_response.json()
    assert body["batch_id"] == batch_id
    assert body["total_jobs"] == 1
    assert body["completed_jobs"] == 1


def test_job_status_endpoint(tmp_path: Path) -> None:
    jobs_file, output_root, batch_id = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    client = create_test_client(tmp_path)
    create_payload = {
        "request_id": "batch-req-job",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    assert client.post("/api/v1/batch", json=create_payload).status_code == 200

    job_response = client.get(
        f"/api/v1/batch/{batch_id}/jobs/job-a",
        params={"output_root": str(output_root)},
    )
    assert job_response.status_code == 200
    body = job_response.json()
    assert body["job_id"] == "job-a"
    assert body["status"] == "completed"


def test_batch_status_not_found(tmp_path: Path) -> None:
    client = create_test_client(tmp_path)
    response = client.get("/api/v1/batch/missing-batch/status")
    assert response.status_code == 404


def test_job_status_not_found(tmp_path: Path) -> None:
    jobs_file, output_root, batch_id = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    client = create_test_client(tmp_path)
    create_payload = {
        "request_id": "batch-req-missing-job",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    assert client.post("/api/v1/batch", json=create_payload).status_code == 200
    response = client.get(
        f"/api/v1/batch/{batch_id}/jobs/missing-job",
        params={"output_root": str(output_root)},
    )
    assert response.status_code == 404


def test_batch_runner_failure_sanitized(tmp_path: Path) -> None:
    jobs_file, output_root, _ = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    config = build_api_config(tmp_path)
    app = create_app(config, batch_inference_runner=failing_run_inference)
    state = create_app_state(config, batch_executor=FailingBatchExecutor(config.service_config))
    app.state.ssri = state
    client = TestClient(app, raise_server_exceptions=False)
    payload = {
        "request_id": "batch-fail",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    response = client.post("/api/v1/batch", json=payload)
    assert response.status_code == 500
    message = response.json()["error"]["message"]
    assert "/etc/" not in message
