"""Tests for authentication bypass attempts and security boundaries."""

from __future__ import annotations


import pytest

from ssri_model.api.config import APIConfig
from ssri_model.auth.config import AuthConfig
from ssri_model.service.config import ServiceConfig
from tests.api_helpers import build_inference_fixture, build_inference_payload
from tests.auth_helpers import auth_header, build_authenticated_api_config, create_authenticated_client


def test_query_parameter_api_key_not_accepted(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="query-key",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    response = client.post(f"/api/v1/inference?api_key={operator_key}", json=payload)
    assert response.status_code == 401


def test_path_traversal_still_rejected_with_auth(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="../evil",
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
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "PATH_SAFETY_VIOLATION"


def test_admin_cannot_bypass_scientific_gate(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    service_config = ServiceConfig(
        output_root=str(tmp_path / "service-outputs"),
        scientific_validation_required=True,
        allow_unvalidated_predictions=False,
        environment="development",
    )
    config = APIConfig(
        service_config=service_config,
        auth_config=config.auth_config,
    )
    client = create_authenticated_client(tmp_path, api_config=config)
    admin_key, _ = keys["admin"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="admin-gate",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
        scientific_validation_status="NOT_VALIDATED",
        scientific_validation_required=True,
    )
    response = client.post(
        "/api/v1/inference",
        json=payload,
        headers=auth_header(admin_key),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SCIENTIFIC_GATE_REJECTED"


def test_production_cannot_create_disabled_auth_config() -> None:
    with pytest.raises(Exception):
        AuthConfig(enabled=False, environment="production")


def test_audit_record_excludes_plaintext_key(tmp_path, caplog) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="audit-test",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    with caplog.at_level("INFO"):
        client.post(
            "/api/v1/inference",
            json=payload,
            headers=auth_header(operator_key),
        )
    combined = "\n".join(record.message for record in caplog.records)
    assert operator_key not in combined
    assert "Authorization" not in combined


def test_key_store_never_returned_by_api(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    for path in ["/health", "/api/v1/health", "/openapi.json"]:
        response = client.get(path, headers=auth_header(operator_key))
        assert response.status_code == 200
        assert "key_hash" not in response.text
