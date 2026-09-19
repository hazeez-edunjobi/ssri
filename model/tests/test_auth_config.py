"""Tests for authentication configuration."""

from __future__ import annotations

import pytest

from ssri_model.auth.config import AuthConfig
from ssri_model.auth.exceptions import InvalidAuthConfigError


def test_production_cannot_disable_auth() -> None:
    with pytest.raises(InvalidAuthConfigError):
        AuthConfig(enabled=False, environment="production")


def test_development_can_disable_auth() -> None:
    config = AuthConfig(enabled=False, environment="development")
    assert config.enabled is False


def test_serialization_roundtrip() -> None:
    config = AuthConfig(enabled=True, environment="staging", key_store_path="auth/keys.json")
    restored = AuthConfig.from_dict(config.to_dict())
    assert restored.enabled is True
    assert restored.environment == "staging"
