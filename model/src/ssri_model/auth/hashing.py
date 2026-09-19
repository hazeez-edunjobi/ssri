"""Secure API key hashing using PBKDF2-HMAC-SHA256."""

from __future__ import annotations

import hashlib
import hmac
import secrets
from base64 import b64decode, b64encode

_ALGORITHM = "pbkdf2_sha256"
_DEFAULT_ITERATIONS = 600_000
_SALT_BYTES = 16
_DERIVED_KEY_BYTES = 32


def hash_api_key_secret(*, secret: str, key_id: str) -> str:
    """Hash an API key secret for secure storage."""
    salt = secrets.token_bytes(_SALT_BYTES)
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        _normalize_secret(secret, key_id),
        salt,
        _DEFAULT_ITERATIONS,
        dklen=_DERIVED_KEY_BYTES,
    )
    salt_encoded = b64encode(salt).decode("ascii")
    derived_encoded = b64encode(derived).decode("ascii")
    return f"{_ALGORITHM}${_DEFAULT_ITERATIONS}${salt_encoded}${derived_encoded}"


def verify_api_key_secret(*, secret: str, key_id: str, key_hash: str) -> bool:
    """Verify a secret against a stored hash."""
    try:
        algorithm, iterations_raw, salt_encoded, derived_encoded = key_hash.split("$", 3)
    except ValueError:
        return False
    if algorithm != _ALGORITHM:
        return False
    try:
        iterations = int(iterations_raw)
        salt = b64decode(salt_encoded.encode("ascii"))
        expected = b64decode(derived_encoded.encode("ascii"))
    except (ValueError, TypeError):
        return False
    derived = hashlib.pbkdf2_hmac(
        "sha256",
        _normalize_secret(secret, key_id),
        salt,
        iterations,
        dklen=len(expected),
    )
    return hmac.compare_digest(derived, expected)


def _normalize_secret(secret: str, key_id: str) -> bytes:
    return f"{key_id}:{secret}".encode("utf-8")
