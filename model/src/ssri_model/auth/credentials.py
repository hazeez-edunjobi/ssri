"""API key generation, parsing, redaction, and key store."""

from __future__ import annotations

import json
import re
import secrets
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ssri_model.auth.exceptions import AuthenticationError, InvalidAuthConfigError
from ssri_model.auth.hashing import hash_api_key_secret
from ssri_model.auth.models import APIKeyRecord, GeneratedAPIKey, Role

API_KEY_PREFIX = "ssri"
_KEY_ID_PATTERN = re.compile(r"^[a-f0-9]{16}$")
_SECRET_MIN_LENGTH = 32


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def generate_api_key(*, role: Role = Role.OPERATOR, description: str = "") -> GeneratedAPIKey:
    """Generate a cryptographically secure API key."""
    key_id = secrets.token_hex(8)
    secret = secrets.token_urlsafe(32)
    plaintext_key = format_api_key(key_id=key_id, secret=secret)
    record = APIKeyRecord(
        key_id=key_id,
        key_hash=hash_api_key_secret(secret=secret, key_id=key_id),
        role=role,
        enabled=True,
        created_at=utc_now_iso(),
        expires_at=None,
        description=description,
    )
    return GeneratedAPIKey(key_id=key_id, plaintext_key=plaintext_key, record=record)


def format_api_key(*, key_id: str, secret: str) -> str:
    return f"{API_KEY_PREFIX}_{key_id}_{secret}"


def parse_api_key(plaintext_key: str) -> tuple[str, str]:
    """Parse a plaintext API key into key_id and secret."""
    normalized = plaintext_key.strip()
    if not normalized.startswith(f"{API_KEY_PREFIX}_"):
        raise AuthenticationError("Invalid authentication credentials.")
    parts = normalized.split("_", 2)
    if len(parts) != 3 or parts[0] != API_KEY_PREFIX:
        raise AuthenticationError("Invalid authentication credentials.")
    key_id, secret = parts[1], parts[2]
    if not _KEY_ID_PATTERN.match(key_id):
        raise AuthenticationError("Invalid authentication credentials.")
    if len(secret) < _SECRET_MIN_LENGTH:
        raise AuthenticationError("Invalid authentication credentials.")
    return key_id, secret


def ensure_key_store_file(path: Path | str) -> Path:
    """Return a readable key-store file, creating an empty store when none exists.

    Production enables API-key auth without always setting ``SSRI_AUTH_KEY_STORE``.
    The default path is ``auth/keys.json``. On the container image, ``/app`` is not
    writable, so a relative path falls back to ``/data/auth/keys.json``.
    An empty store rejects every API key. It does not disable authentication.
    """
    store_path = Path(path)
    if store_path.is_file():
        return store_path
    candidates = [store_path]
    container_store = Path("/data/auth/keys.json")
    if store_path == Path("auth/keys.json") and container_store.parent.is_dir():
        candidates.append(container_store)
    last_error: OSError | None = None
    for candidate in candidates:
        try:
            candidate.parent.mkdir(parents=True, exist_ok=True)
            if not candidate.exists():
                candidate.write_text('{"keys": []}\n', encoding="utf-8")
            return candidate
        except OSError as exc:
            last_error = exc
    raise InvalidAuthConfigError(
        "Authentication key store could not be created. "
        "Set SSRI_AUTH_KEY_STORE to a writable path."
    ) from last_error


def redact_api_key(plaintext_key: str) -> str:
    """Return a redacted representation safe for logs."""
    try:
        key_id, _ = parse_api_key(plaintext_key)
    except AuthenticationError:
        return f"{API_KEY_PREFIX}_********_********"
    return f"{API_KEY_PREFIX}_{key_id}_********"


@dataclass
class KeyStore:
    """Read-only in-memory API key store."""

    path: Path | None
    records: dict[str, APIKeyRecord] = field(default_factory=dict)

    @classmethod
    def load(cls, path: Path | str) -> KeyStore:
        store_path = ensure_key_store_file(path)
        if not store_path.is_file():
            raise InvalidAuthConfigError("Authentication key store not found")
        try:
            payload = json.loads(store_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidAuthConfigError("Unable to read authentication key store") from exc
        if not isinstance(payload, dict):
            raise InvalidAuthConfigError("Authentication key store must contain a JSON object")
        raw_keys = payload.get("keys")
        if not isinstance(raw_keys, list):
            raise InvalidAuthConfigError("Authentication key store must contain a keys array")
        records: dict[str, APIKeyRecord] = {}
        for index, entry in enumerate(raw_keys):
            if not isinstance(entry, dict):
                raise InvalidAuthConfigError(f"Key entry at index {index} must be an object")
            record = APIKeyRecord.from_dict(entry)
            records[record.key_id] = record
        return cls(path=store_path, records=records)

    @classmethod
    def from_records(cls, records: Mapping[str, APIKeyRecord]) -> KeyStore:
        return cls(path=None, records=dict(records))

    def get(self, key_id: str) -> APIKeyRecord | None:
        return self.records.get(key_id)

    def to_dict(self) -> dict[str, Any]:
        return {"keys": [record.to_dict() for record in self.records.values()]}

    @staticmethod
    def write(path: Path | str, records: list[APIKeyRecord]) -> None:
        """Persist key records without plaintext secrets (provisioning helper)."""
        store_path = Path(path)
        store_path.parent.mkdir(parents=True, exist_ok=True)
        payload = {"keys": [record.to_dict() for record in records]}
        store_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def is_key_active(record: APIKeyRecord, *, now: datetime | None = None) -> bool:
    if not record.enabled:
        return False
    if record.expires_at:
        current = now or datetime.now(timezone.utc)
        try:
            expiry = datetime.fromisoformat(record.expires_at)
            if expiry.tzinfo is None:
                expiry = expiry.replace(tzinfo=timezone.utc)
        except ValueError:
            return False
        if current >= expiry:
            return False
    return True
