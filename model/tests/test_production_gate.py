"""Production fail-closed gate tests."""

from __future__ import annotations

import json

import pytest

from ssri_model.auth.credentials import KeyStore, ensure_key_store_file
from ssri_model.api.production_gate import (
    UnsafeProductionConfigError,
    assert_production_safe,
    validate_production_environment,
)


def test_development_is_allowed_with_auth_disabled() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "development",
            "SSRI_AUTH_ENABLED": "false",
        }
    )
    assert result.ok is True


def test_production_rejects_disabled_auth() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "false",
            "SSRI_CORS_ORIGINS": "https://app.example.com",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
            "SSRI_AUTH_KEY_STORE": "auth/keys.json",
        }
    )
    assert result.ok is False
    assert any("SSRI_AUTH_ENABLED" in err for err in result.errors)


def test_production_rejects_wildcard_cors() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "true",
            "SSRI_CORS_ORIGINS": "*",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
            "SSRI_AUTH_KEY_STORE": "auth/keys.json",
        }
    )
    assert result.ok is False
    assert any("Wildcard CORS" in err for err in result.errors)


def test_production_uses_default_key_store_when_unset() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "true",
            "SSRI_CORS_ORIGINS": "https://app.example.com",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
        }
    )
    assert result.ok is True


def test_production_rejects_blank_key_store() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "true",
            "SSRI_CORS_ORIGINS": "https://app.example.com",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
            "SSRI_AUTH_KEY_STORE": "  ",
        }
    )
    assert result.ok is False
    assert any("SSRI_AUTH_KEY_STORE" in err for err in result.errors)


def test_production_safe_config_passes() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "true",
            "SSRI_CORS_ORIGINS": "https://app.example.com",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
            "SSRI_AUTH_KEY_STORE": "auth/keys.json",
        }
    )
    assert result.ok is True


def test_production_rejects_short_jwt_secret() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "true",
            "SSRI_CORS_ORIGINS": "https://app.example.com",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
            "SSRI_AUTH_KEY_STORE": "auth/keys.json",
            "SSRI_JWT_SECRET": "short",
        }
    )
    assert result.ok is False
    assert any("JWT secret" in err for err in result.errors)


def test_production_rejects_s3_without_bucket() -> None:
    result = validate_production_environment(
        {
            "SSRI_API_ENVIRONMENT": "production",
            "SSRI_AUTH_ENABLED": "true",
            "SSRI_CORS_ORIGINS": "https://app.example.com",
            "SSRI_AUTH_DEVELOPMENT_MODE": "false",
            "SSRI_AUTH_KEY_STORE": "auth/keys.json",
            "SSRI_OBJECT_STORAGE_BACKEND": "s3",
            "SSRI_OBJECT_STORAGE_BUCKET": "",
        }
    )
    assert result.ok is False
    assert any("SSRI_OBJECT_STORAGE_BUCKET" in err for err in result.errors)


def test_missing_key_store_file_is_created_empty(tmp_path) -> None:
    created = ensure_key_store_file(tmp_path / "keys.json")
    assert json.loads(created.read_text(encoding="utf-8")) == {"keys": []}
    assert KeyStore.load(created).records == {}


def test_create_app_production_starts_without_key_store_env(tmp_path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("SSRI_API_ENVIRONMENT", "production")
    monkeypatch.setenv("SSRI_AUTH_ENABLED", "true")
    monkeypatch.setenv("SSRI_AUTH_DEVELOPMENT_MODE", "false")
    monkeypatch.setenv("SSRI_CORS_ORIGINS", "https://app.example.com")
    monkeypatch.setenv("SSRI_API_OUTPUT_ROOT", str(tmp_path / "outputs"))
    monkeypatch.setenv("SSRI_EXECUTION_MODE", "local")
    monkeypatch.delenv("SSRI_AUTH_KEY_STORE", raising=False)
    from ssri_model.api.app import create_app

    app = create_app()
    assert app.title == "SSRI Model API"
    assert json.loads((tmp_path / "auth" / "keys.json").read_text(encoding="utf-8")) == {"keys": []}


def test_assert_raises() -> None:
    with pytest.raises(UnsafeProductionConfigError):
        assert_production_safe(
            {
                "SSRI_API_ENVIRONMENT": "production",
                "SSRI_AUTH_ENABLED": "false",
            }
        )
