"""Tests for API key credentials and key store."""

from __future__ import annotations


from ssri_model.auth.credentials import (
    KeyStore,
    generate_api_key,
    parse_api_key,
    redact_api_key,
)
from ssri_model.auth.models import Role


def test_generate_api_key_format() -> None:
    generated = generate_api_key(role=Role.OPERATOR)
    assert generated.plaintext_key.startswith("ssri_")
    key_id, secret = parse_api_key(generated.plaintext_key)
    assert key_id == generated.key_id
    assert len(secret) >= 32


def test_generated_keys_are_not_deterministic() -> None:
    first = generate_api_key()
    second = generate_api_key()
    assert first.plaintext_key != second.plaintext_key


def test_redact_api_key() -> None:
    generated = generate_api_key()
    redacted = redact_api_key(generated.plaintext_key)
    assert generated.plaintext_key not in redacted
    assert "********" in redacted


def test_key_store_roundtrip(tmp_path) -> None:
    generated = generate_api_key(role=Role.VIEWER)
    path = tmp_path / "keys.json"
    KeyStore.write(path, [generated.record])
    store = KeyStore.load(path)
    loaded = store.get(generated.key_id)
    assert loaded is not None
    assert loaded.key_hash == generated.record.key_hash
    assert "plaintext" not in path.read_text(encoding="utf-8")
