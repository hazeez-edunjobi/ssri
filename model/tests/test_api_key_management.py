"""Tests for Stage 3.3 API key management."""

from __future__ import annotations

import json
from pathlib import Path

from tests.api_helpers import build_inference_fixture, build_inference_payload
from tests.auth_helpers import auth_header
from tests.operational_helpers import (
    build_operational_api_config,
    create_operational_client,
    key_store_contains_secret,
    read_key_store_plaintext,
)


def test_create_api_key_returns_plaintext_once(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    admin_key, _ = keys["admin"]
    store_path = keys["store_path"]
    assert isinstance(store_path, Path)

    response = client.post(
        "/api/v1/auth/keys",
        json={"role": "operator", "name": "production-inference"},
        headers=auth_header(admin_key),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["key_id"]
    assert body["api_key"].startswith("ssri_")
    assert body["role"] == "operator"
    assert "created_at" in body

    stored = json.loads(read_key_store_plaintext(store_path))
    serialized = json.dumps(stored)
    assert body["api_key"] not in serialized
    assert key_store_contains_secret(store_path, body["api_key"]) is False


def test_list_and_get_keys_never_return_secret(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    admin_key, _ = keys["admin"]

    created = client.post(
        "/api/v1/auth/keys",
        json={"role": "viewer", "name": "read-only"},
        headers=auth_header(admin_key),
    ).json()
    api_key = created["api_key"]
    key_id = created["key_id"]

    listed = client.get("/api/v1/auth/keys", headers=auth_header(admin_key))
    assert listed.status_code == 200
    listed_text = listed.text
    assert api_key not in listed_text
    assert "api_key" not in listed.json()[0]

    fetched = client.get(f"/api/v1/auth/keys/{key_id}", headers=auth_header(admin_key))
    assert fetched.status_code == 200
    assert "api_key" not in fetched.json()
    assert api_key not in fetched.text


def test_disable_enable_delete_key_lifecycle(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    admin_key, _ = keys["admin"]

    created = client.post(
        "/api/v1/auth/keys",
        json={"role": "operator", "name": "temp"},
        headers=auth_header(admin_key),
    ).json()
    key_id = created["key_id"]
    api_key = created["api_key"]

    disabled = client.post(
        f"/api/v1/auth/keys/{key_id}/disable",
        headers=auth_header(admin_key),
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False

    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)
    payload = build_inference_payload(
        request_id="disabled-key",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    assert (
        client.post("/api/v1/inference", json=payload, headers=auth_header(api_key)).status_code
        == 401
    )

    enabled = client.post(
        f"/api/v1/auth/keys/{key_id}/enable",
        headers=auth_header(admin_key),
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert (
        client.post("/api/v1/inference", json=payload, headers=auth_header(api_key)).status_code
        == 200
    )

    deleted = client.delete(f"/api/v1/auth/keys/{key_id}", headers=auth_header(admin_key))
    assert deleted.status_code == 204
    assert client.get(f"/api/v1/auth/keys/{key_id}", headers=auth_header(admin_key)).status_code == 404


def test_key_management_requires_manage_auth(tmp_path) -> None:
    config, keys = build_operational_api_config(tmp_path)
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    viewer_key, _ = keys["viewer"]

    for key in (operator_key, viewer_key):
        response = client.post(
            "/api/v1/auth/keys",
            json={"role": "operator"},
            headers=auth_header(key),
        )
        assert response.status_code == 403
        assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
