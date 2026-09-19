"""Redis-backed distributed idempotency store with TTL enforcement."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from ssri_model.jobs.exceptions import IdempotencyConflictError
from ssri_model.jobs.idempotency import IdempotencyEntry, validate_idempotency_key
from ssri_model.service.validation import sanitize_request_id

if TYPE_CHECKING:
    import redis

_KEY_PREFIX = "ssri:idempotency"


class RedisIdempotencyStore:
    """Principal-scoped idempotency backed by Redis with enforced expiry."""

    def __init__(self, client: redis.Redis, *, ttl_seconds: int) -> None:
        self._client = client
        self._ttl_seconds = ttl_seconds

    def _key(self, principal_key_id: str, idempotency_key: str) -> str:
        safe_principal = sanitize_request_id(principal_key_id)
        safe_key = validate_idempotency_key(idempotency_key)
        digest = hashlib.sha256(f"{safe_principal}:{safe_key}".encode("utf-8")).hexdigest()
        return f"{_KEY_PREFIX}:{safe_principal}:{digest}"

    def get(self, *, principal_key_id: str, idempotency_key: str) -> IdempotencyEntry | None:
        raw = self._client.get(self._key(principal_key_id, idempotency_key))
        if raw is None:
            return None
        payload = json.loads(str(raw))
        return IdempotencyEntry(
            principal_key_id=str(payload["principal_key_id"]),
            idempotency_key=str(payload["idempotency_key"]),
            job_id=str(payload["job_id"]),
            request_fingerprint=str(payload["request_fingerprint"]),
            created_at=str(payload["created_at"]),
        )

    def put(
        self,
        *,
        principal_key_id: str,
        idempotency_key: str,
        job_id: str,
        request_fingerprint: str,
    ) -> IdempotencyEntry:
        key = self._key(principal_key_id, idempotency_key)
        existing_raw = self._client.get(key)
        if existing_raw is not None:
            existing = json.loads(str(existing_raw))
            if existing["request_fingerprint"] != request_fingerprint:
                raise IdempotencyConflictError("Idempotency key conflict")
            return IdempotencyEntry(
                principal_key_id=str(existing["principal_key_id"]),
                idempotency_key=str(existing["idempotency_key"]),
                job_id=str(existing["job_id"]),
                request_fingerprint=str(existing["request_fingerprint"]),
                created_at=str(existing["created_at"]),
            )
        entry = IdempotencyEntry(
            principal_key_id=principal_key_id,
            idempotency_key=validate_idempotency_key(idempotency_key),
            job_id=job_id,
            request_fingerprint=request_fingerprint,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        created = self._client.set(
            key,
            json.dumps(entry.to_dict()),
            nx=True,
            ex=self._ttl_seconds,
        )
        if not created:
            return self.put(
                principal_key_id=principal_key_id,
                idempotency_key=idempotency_key,
                job_id=job_id,
                request_fingerprint=request_fingerprint,
            )
        return entry
