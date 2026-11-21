"""Assess accepts Supabase/session bearers with least-privilege USER role."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from ssri_model.auth.dependencies import authenticate_supabase_bearer, role_from_platform_role
from ssri_model.auth.exceptions import AuthenticationError
from ssri_model.auth.models import Permission, Role
from ssri_model.platform.auth import looks_like_jwt, verify_supabase_access_token
from ssri_model.platform.store import PlatformError
from tests.auth_helpers import auth_header, build_authenticated_api_config, create_authenticated_client


def test_assess_requires_auth_when_enabled(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path, enabled=True)
    client = create_authenticated_client(tmp_path, api_config=config)
    response = client.post(
        "/api/v1/assess",
        json={"point": {"lat": 6.5, "lon": 3.4}, "mc_samples": 2},
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_assess_rejects_invalid_api_key(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    response = client.post(
        "/api/v1/assess",
        json={"point": {"lat": 6.5, "lon": 3.4}, "mc_samples": 2},
        headers=auth_header("ssri_abcd1234abcd1234_wrongsecretvalue123456789012345"),
    )
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "INVALID_CREDENTIALS"


def test_assess_rejects_viewer_api_key(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    viewer_key, _ = keys["viewer"]
    response = client.post(
        "/api/v1/assess",
        json={"point": {"lat": 6.5, "lon": 3.4}, "mc_samples": 2},
        headers=auth_header(viewer_key),
    )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"


def test_assess_accepts_signed_in_user_session(tmp_path) -> None:
    """Platform role ``user`` maps to Role.USER with RUN_ASSESS only."""
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    client.app.state.platform_tokens = {
        "session-assess-token": ("user-assess-1", "assess@example.com", "user"),
    }
    response = client.post(
        "/api/v1/assess",
        json={"point": {"lat": 6.5244, "lon": 3.3792}, "mc_samples": 2},
        headers=auth_header("session-assess-token"),
    )
    assert response.status_code != 401
    assert response.status_code != 403
    assert response.status_code in {200, 400, 422, 503}


def test_assess_accepts_operator_api_key(tmp_path) -> None:
    config, keys = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    response = client.post(
        "/api/v1/assess",
        json={"point": {"lat": 6.5244, "lon": 3.3792}, "mc_samples": 2},
        headers=auth_header(operator_key),
    )
    assert response.status_code != 401
    assert response.status_code != 403


def test_user_session_can_list_geological_but_not_mutate(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    client.app.state.platform_tokens = {
        "session-geo-user": ("user-geo-1", "geo@example.com", "user"),
    }
    headers = auth_header("session-geo-user")
    listed = client.get("/api/v1/geological/datasets", headers=headers)
    assert listed.status_code == 200
    created = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "blocked", "asset_kind": "point_grid_csv"},
        headers=headers,
    )
    assert created.status_code == 403
    assert created.json()["error"]["code"] == "INSUFFICIENT_PERMISSIONS"
    applied = client.post(
        "/api/v1/geological/apply/offline",
        json={"geo_ids": ["x"], "target_dataset_id": "y"},
        headers=headers,
    )
    assert applied.status_code == 403


def test_operator_session_can_mutate_geological(tmp_path) -> None:
    config, _ = build_authenticated_api_config(tmp_path)
    client = create_authenticated_client(tmp_path, api_config=config)
    client.app.state.platform_tokens = {
        "session-geo-op": ("op-geo-1", "op@example.com", "operator"),
    }
    response = client.post(
        "/api/v1/geological/datasets",
        json={"display_name": "allowed", "asset_kind": "point_grid_csv"},
        headers=auth_header("session-geo-op"),
    )
    assert response.status_code == 201


def test_unknown_platform_role_fails_closed() -> None:
    with pytest.raises(AuthenticationError):
        role_from_platform_role("superuser")


def test_authenticate_supabase_bearer_user_is_not_operator() -> None:
    principal = authenticate_supabase_bearer(
        "tok",
        platform_tokens={"tok": ("u1", "a@b.c", "user")},
    )
    assert principal.role == Role.USER
    assert Permission.RUN_ASSESS in principal.permissions
    assert Permission.RUN_INFERENCE not in principal.permissions
    assert Permission.MANAGE_GEOLOGICAL not in principal.permissions


def test_looks_like_jwt_rejects_api_keys_and_malformed() -> None:
    assert not looks_like_jwt("ssri_abcd1234abcd1234_secretsecretsecretsecret1234")
    assert not looks_like_jwt("not-a-jwt")
    assert not looks_like_jwt("")
    assert looks_like_jwt("aaa.bbb.ccc")


def test_verify_supabase_rejects_malformed_without_network(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    with pytest.raises(PlatformError) as exc:
        verify_supabase_access_token("not-a-jwt")
    assert exc.value.status == 401


def test_verify_supabase_rejects_http_401(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    mock_response = MagicMock()
    mock_response.status_code = 401
    mock_response.json.return_value = {}
    with patch("ssri_model.platform.auth.httpx.get", return_value=mock_response):
        with pytest.raises(PlatformError) as exc:
            verify_supabase_access_token("aaa.bbb.ccc")
    assert exc.value.status == 401


def test_verify_supabase_accepts_valid_user_payload(monkeypatch) -> None:
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "anon-test-key")
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json.return_value = {
        "id": "11111111-1111-1111-1111-111111111111",
        "email": "user@example.com",
        "user_metadata": {"display_name": "User"},
    }
    with patch("ssri_model.platform.auth.httpx.get", return_value=mock_response) as get:
        identity = verify_supabase_access_token("aaa.bbb.ccc")
    assert identity.user_id.startswith("1111")
    # Ensure the call targeted the configured project URL (project binding).
    assert get.call_args.args[0].startswith("https://example.supabase.co/auth/v1/user")
