"""Integration tests for API authorization."""

from __future__ import annotations

from tests.api_helpers import build_batch_fixture, build_inference_fixture, build_inference_payload
from tests.auth_helpers import auth_header, build_authenticated_api_config, create_authenticated_client


def test_viewer_cannot_run_inference(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    viewer_key, _ = keys["viewer"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="viewer-infer",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post(
        "/api/v1/inference",
        json=payload,
        headers=auth_header(viewer_key),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_viewer_cannot_run_batch(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    viewer_key, _ = keys["viewer"]
    jobs_file, output_root, _ = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": "viewer-batch",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    response = client.post(
        "/api/v1/batch",
        json=payload,
        headers=auth_header(viewer_key),
    )
    assert response.status_code == 403


def test_operator_can_run_batch(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    jobs_file, output_root, _ = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    payload = {
        "request_id": "operator-batch",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    response = client.post(
        "/api/v1/batch",
        json=payload,
        headers=auth_header(operator_key),
    )
    assert response.status_code == 200


def test_viewer_can_read_batch_status(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    viewer_key, _ = keys["viewer"]
    jobs_file, output_root, batch_id = build_batch_fixture(tmp_path)
    output_root.mkdir(parents=True, exist_ok=True)
    create_payload = {
        "request_id": "auth-batch-status",
        "jobs_file": str(jobs_file),
        "output_root": str(output_root),
    }
    assert client.post(
        "/api/v1/batch",
        json=create_payload,
        headers=auth_header(operator_key),
    ).status_code == 200
    response = client.get(
        f"/api/v1/batch/{batch_id}/status",
        params={"output_root": str(output_root)},
        headers=auth_header(viewer_key),
    )
    assert response.status_code == 200


def test_admin_has_operator_permissions(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    admin_key, _ = keys["admin"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="admin-infer",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post(
        "/api/v1/inference",
        json=payload,
        headers=auth_header(admin_key),
    )
    assert response.status_code == 200
