"""Tests for Stage 3.3 async jobs, idempotency, and ownership."""

from __future__ import annotations

import json
from pathlib import Path

from tests.api_helpers import (
    FailingInferenceExecutor,
    build_batch_fixture,
    build_inference_fixture,
    build_inference_payload,
)
from tests.auth_helpers import auth_header
from tests.operational_helpers import (
    build_operational_api_config,
    create_operational_client,
    wait_for_job_status,
)


def _async_inference_payload(tmp_path: Path, request_id: str) -> dict[str, object]:
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    return build_inference_payload(
        request_id=request_id,
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )


def test_async_inference_returns_202_and_completes(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)

    response = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "async-req-1"),
        headers=headers,
    )
    assert response.status_code == 202
    body = response.json()
    assert body["status"] == "queued"
    assert body["job_id"].startswith("job-")
    assert body["status_url"] == f"/api/v1/jobs/{body['job_id']}"

    final = wait_for_job_status(client, body["job_id"], headers=headers)
    assert final["status"] == "completed"
    assert final["artifacts"]["prediction"]


def test_async_batch_returns_202_and_completes(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)
    jobs_file, output_root, _ = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)

    response = client.post(
        "/api/v1/batch/async",
        json={
            "request_id": "async-batch-1",
            "jobs_file": str(jobs_file),
            "output_root": str(output_root),
        },
        headers=headers,
    )
    assert response.status_code == 202
    job_id = response.json()["job_id"]
    final = wait_for_job_status(client, job_id, headers=headers)
    assert final["status"] == "completed"
    assert final["artifacts"]["manifest_path"]


def test_job_ownership_isolation(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, operator_record = keys["operator"]
    admin_key, _ = keys["admin"]

    submitted = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "ownership-req"),
        headers=auth_header(operator_key),
    ).json()
    job_id = submitted["job_id"]

    other_config, other_keys = build_operational_api_config(tmp_path / "other")
    other_client = create_operational_client(tmp_path / "other", api_config=other_config)
    other_operator_key, _ = other_keys["operator"]
    denied = other_client.get(f"/api/v1/jobs/{job_id}", headers=auth_header(other_operator_key))
    assert denied.status_code == 404

    allowed = client.get(f"/api/v1/jobs/{job_id}", headers=auth_header(admin_key))
    assert allowed.status_code == 200
    assert allowed.json()["submitted_by_key_id"] == operator_record.key_id


def test_idempotency_returns_same_job(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = {**auth_header(operator_key), "Idempotency-Key": "idem-001"}
    payload = _async_inference_payload(tmp_path, "idem-req")

    first = client.post("/api/v1/inference/async", json=payload, headers=headers)
    second = client.post("/api/v1/inference/async", json=payload, headers=headers)
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] == second.json()["job_id"]


def test_idempotency_cross_user_isolation(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    admin_key, _ = keys["admin"]
    payload = _async_inference_payload(tmp_path, "idem-cross-user")

    first = client.post(
        "/api/v1/inference/async",
        json=payload,
        headers={**auth_header(operator_key), "Idempotency-Key": "shared-key"},
    )
    second = client.post(
        "/api/v1/inference/async",
        json=payload,
        headers={**auth_header(admin_key), "Idempotency-Key": "shared-key"},
    )
    assert first.status_code == 202
    assert second.status_code == 202
    assert first.json()["job_id"] != second.json()["job_id"]


def test_idempotency_conflict_on_different_payload(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = {**auth_header(operator_key), "Idempotency-Key": "conflict-key"}

    first_payload = _async_inference_payload(tmp_path, "conflict-a")
    second_payload = _async_inference_payload(tmp_path, "conflict-b")
    assert client.post("/api/v1/inference/async", json=first_payload, headers=headers).status_code == 202
    conflict = client.post("/api/v1/inference/async", json=second_payload, headers=headers)
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"


def test_cancel_queued_job(tmp_path) -> None:
    import threading
    from ssri_model.api.app import create_app
    from ssri_model.inference import InferenceConfig
    from tests.orchestration_helpers import mock_run_inference

    gate = threading.Event()

    def blocking_run_inference(config: InferenceConfig):
        gate.wait(timeout=5.0)
        return mock_run_inference(config)

    config, keys = build_operational_api_config(tmp_path, worker_count=1, max_queue_size=100)
    app = create_app(
        config,
        inference_runner=blocking_run_inference,
        batch_inference_runner=blocking_run_inference,
    )
    from fastapi.testclient import TestClient

    client = TestClient(app)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)

    first = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "cancel-block-1"),
        headers=headers,
    ).json()
    second = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "cancel-block-2"),
        headers=headers,
    ).json()

    cancelled = client.post(f"/api/v1/jobs/{second['job_id']}/cancel", headers=headers)
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"

    gate.set()
    final = wait_for_job_status(client, first["job_id"], headers=headers)
    assert final["status"] == "completed"


def test_job_persistence_on_disk(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)

    submitted = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "persist-req"),
        headers=headers,
    ).json()
    job_id = submitted["job_id"]
    wait_for_job_status(client, job_id, headers=headers)

    job_path = Path(config.output_root) / "jobs" / job_id / "job.json"
    assert job_path.is_file()
    payload = json.loads(job_path.read_text(encoding="utf-8"))
    assert payload["job_id"] == job_id
    assert payload["status"] == "completed"
    assert (job_path.parent / "result.json").is_file()


def test_async_disabled_returns_503(tmp_path) -> None:
    base_config, keys = build_operational_api_config(tmp_path, async_enabled=False)
    client = create_operational_client(tmp_path, api_config=base_config)
    operator_key, _ = keys["operator"]
    response = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "async-disabled"),
        headers=auth_header(operator_key),
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ASYNC_DISABLED"


def test_failed_job_sanitized_error(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    from ssri_model.api.app import create_app
    from tests.orchestration_helpers import mock_run_inference

    app = create_app(
        config,
        inference_runner=mock_run_inference,
        batch_inference_runner=mock_run_inference,
        inference_executor=FailingInferenceExecutor(config.service_config),
    )
    from fastapi.testclient import TestClient

    client = TestClient(app)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)

    submitted = client.post(
        "/api/v1/inference/async",
        json=_async_inference_payload(tmp_path, "fail-req"),
        headers=headers,
    ).json()
    final = wait_for_job_status(client, submitted["job_id"], headers=headers, expected={"failed"})
    assert final["status"] == "failed"
    assert final["error_code"] == "INFERENCE_FAILED"
    assert "secret" not in str(final.get("error_message", "")).lower()
