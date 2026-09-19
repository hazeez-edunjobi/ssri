"""Integration tests for API authentication."""

from __future__ import annotations


from tests.api_helpers import build_inference_fixture, build_inference_payload
from tests.auth_helpers import auth_header, build_authenticated_api_config, create_authenticated_client


def test_health_public_without_auth(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 200
    assert client.get("/api/v1/ready").status_code == 200


def test_inference_requires_auth_when_enabled(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path, enabled=True)
    client = create_authenticated_client(tmp_path, api_config=config)
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="auth-req",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"
    assert response.headers.get("WWW-Authenticate") == "Bearer"


def test_inference_invalid_key_returns_401(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="auth-invalid",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post(
        "/api/v1/inference",
        json=payload,
        headers=auth_header("ssri_abcd1234abcd1234_wrongsecretvalue123456789012345"),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_inference_success_with_operator_key(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="auth-success",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post(
        "/api/v1/inference",
        json=payload,
        headers=auth_header(operator_key),
    )
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "completed"
    assert body["provenance"]["auth_key_id"] is not None


def test_auth_disabled_uses_development_principal(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path, enabled=False)
    client = create_authenticated_client(tmp_path, api_config=config)
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="auth-disabled",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post("/api/v1/inference", json=payload)
    assert response.status_code == 200


def test_malformed_authorization_header(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    response = client.post(
        "/api/v1/inference",
        json={"request_id": "x"},
        headers={"Authorization": "Token abc"},
    )
    assert response.status_code == 401


def test_api_config_serialization_contains_no_secrets(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    operator_key, _ = keys["operator"]
    serialized = str(config.to_dict())
    assert operator_key not in serialized
