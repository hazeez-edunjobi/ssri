"""Tests for authentication dependencies."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from ssri_model.auth.config import AuthConfig
from ssri_model.auth.credentials import KeyStore, generate_api_key
from ssri_model.auth.dependencies import authenticate_api_key, extract_bearer_token
from ssri_model.auth.exceptions import AuthenticationError
from ssri_model.auth.models import APIKeyRecord, Role
from fastapi.security import HTTPAuthorizationCredentials


def test_extract_bearer_token_success() -> None:
    credentials = HTTPAuthorizationCredentials(scheme="Bearer", credentials="ssri_test")
    assert extract_bearer_token(credentials) == "ssri_test"


def test_extract_bearer_token_missing() -> None:
    with pytest.raises(AuthenticationError):
        extract_bearer_token(None)


def test_authenticate_valid_key() -> None:
    generated = generate_api_key(role=Role.OPERATOR)
    store = KeyStore.from_records({generated.key_id: generated.record})
    principal = authenticate_api_key(
        auth_config=AuthConfig(enabled=True, key_store_path="auth/keys.json"),
        key_store=store,
        token=generated.plaintext_key,
    )
    assert principal.role == Role.OPERATOR


def test_authenticate_disabled_key() -> None:
    generated = generate_api_key(role=Role.OPERATOR)
    disabled = APIKeyRecord(
        key_id=generated.key_id,
        key_hash=generated.record.key_hash,
        role=Role.OPERATOR,
        enabled=False,
    )
    store = KeyStore.from_records({generated.key_id: disabled})
    with pytest.raises(AuthenticationError):
        authenticate_api_key(
            auth_config=AuthConfig(enabled=True, key_store_path="auth/keys.json"),
            key_store=store,
            token=generated.plaintext_key,
        )


def test_authenticate_expired_key() -> None:
    generated = generate_api_key(role=Role.OPERATOR)
    expired = APIKeyRecord(
        key_id=generated.key_id,
        key_hash=generated.record.key_hash,
        role=Role.OPERATOR,
        enabled=True,
        expires_at=(datetime.now(timezone.utc) - timedelta(days=1)).isoformat(),
    )
    store = KeyStore.from_records({generated.key_id: expired})
    with pytest.raises(AuthenticationError):
        authenticate_api_key(
            auth_config=AuthConfig(enabled=True, key_store_path="auth/keys.json"),
            key_store=store,
            token=generated.plaintext_key,
        )
