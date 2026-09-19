"""Tests for API key hashing."""

from __future__ import annotations

from ssri_model.auth.hashing import hash_api_key_secret, verify_api_key_secret


def test_hash_and_verify_success() -> None:
    secret = "super-secret-token-with-enough-length-123456"
    key_id = "abcd1234abcd1234"
    key_hash = hash_api_key_secret(secret=secret, key_id=key_id)
    assert verify_api_key_secret(secret=secret, key_id=key_id, key_hash=key_hash)


def test_wrong_secret_fails_verification() -> None:
    key_hash = hash_api_key_secret(secret="correct-secret-value-123456789012345", key_id="abcd1234abcd1234")
    assert not verify_api_key_secret(
        secret="wrong-secret-value-1234567890123456",
        key_id="abcd1234abcd1234",
        key_hash=key_hash,
    )
