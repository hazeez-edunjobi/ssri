"""Production fail-closed gate tests."""

from __future__ import annotations

import pytest

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


def test_assert_raises() -> None:
    with pytest.raises(UnsafeProductionConfigError):
        assert_production_safe(
            {
                "SSRI_API_ENVIRONMENT": "production",
                "SSRI_AUTH_ENABLED": "false",
            }
        )
