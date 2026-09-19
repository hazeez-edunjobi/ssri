"""Mutable API key store management."""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from ssri_model.auth.audit import log_auth_management_event
from ssri_model.auth.credentials import KeyStore, generate_api_key, utc_now_iso
from ssri_model.auth.exceptions import InvalidAuthConfigError
from ssri_model.auth.models import APIKeyRecord, GeneratedAPIKey, Role


class KeyStoreManager:
    """Thread-safe mutable key store backed by a JSON file."""

    def __init__(self, store: KeyStore) -> None:
        self._store = store
        self._lock = threading.Lock()

    @classmethod
    def load(cls, path: Path | str) -> KeyStoreManager:
        return cls(KeyStore.load(path))

    @classmethod
    def from_store(cls, store: KeyStore) -> KeyStoreManager:
        return cls(store)

    def _persist(self) -> None:
        if self._store.path is None:
            raise InvalidAuthConfigError("Key store path is not configured")
        payload = self._store.to_dict()
        tmp_path = self._store.path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        os.replace(tmp_path, self._store.path)

    def list_keys(self) -> list[APIKeyRecord]:
        with self._lock:
            return list(self._store.records.values())

    def get_key(self, key_id: str) -> APIKeyRecord | None:
        with self._lock:
            return self._store.get(key_id)

    def create_key(
        self,
        *,
        role: Role,
        name: str = "",
        expires_at: str | None = None,
        actor_key_id: str | None = None,
    ) -> GeneratedAPIKey:
        with self._lock:
            generated = generate_api_key(role=role, description=name)
            record = APIKeyRecord(
                key_id=generated.key_id,
                key_hash=generated.record.key_hash,
                role=role,
                enabled=True,
                created_at=utc_now_iso(),
                expires_at=expires_at,
                description=name,
            )
            if record.key_id in self._store.records:
                raise InvalidAuthConfigError("Duplicate key identifier")
            self._store.records[record.key_id] = record
            self._persist()
            log_auth_management_event(
                event="key_created",
                key_id=record.key_id,
                actor_key_id=actor_key_id,
                role=role.value,
                outcome="success",
            )
            return GeneratedAPIKey(
                key_id=record.key_id,
                plaintext_key=generated.plaintext_key,
                record=record,
            )

    def disable_key(self, key_id: str, *, actor_key_id: str | None = None) -> APIKeyRecord:
        return self._set_enabled(key_id, enabled=False, actor_key_id=actor_key_id, event="key_disabled")

    def enable_key(self, key_id: str, *, actor_key_id: str | None = None) -> APIKeyRecord:
        return self._set_enabled(key_id, enabled=True, actor_key_id=actor_key_id, event="key_enabled")

    def delete_key(self, key_id: str, *, actor_key_id: str | None = None) -> None:
        with self._lock:
            record = self._store.get(key_id)
            if record is None:
                raise InvalidAuthConfigError("Key not found")
            del self._store.records[key_id]
            self._persist()
            log_auth_management_event(
                event="key_deleted",
                key_id=key_id,
                actor_key_id=actor_key_id,
                role=record.role.value,
                outcome="success",
            )

    def _set_enabled(
        self,
        key_id: str,
        *,
        enabled: bool,
        actor_key_id: str | None,
        event: str,
    ) -> APIKeyRecord:
        with self._lock:
            record = self._store.get(key_id)
            if record is None:
                raise InvalidAuthConfigError("Key not found")
            updated = APIKeyRecord(
                key_id=record.key_id,
                key_hash=record.key_hash,
                role=record.role,
                enabled=enabled,
                created_at=record.created_at,
                expires_at=record.expires_at,
                description=record.description,
            )
            self._store.records[key_id] = updated
            self._persist()
            log_auth_management_event(
                event=event,
                key_id=key_id,
                actor_key_id=actor_key_id,
                role=record.role.value,
                outcome="success",
            )
            return updated

    def reload(self) -> None:
        if self._store.path is None:
            return
        with self._lock:
            self._store = KeyStore.load(self._store.path)

    @property
    def readonly_store(self) -> KeyStore:
        return self._store
