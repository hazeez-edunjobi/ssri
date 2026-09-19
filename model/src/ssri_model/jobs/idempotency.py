"""Idempotency mapping for async submissions."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from ssri_model.jobs.exceptions import IdempotencyConflictError
from ssri_model.service.validation import reject_null_bytes, sanitize_request_id

_SAFE_IDEMPOTENCY_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


@dataclass(frozen=True)
class IdempotencyEntry:
    principal_key_id: str
    idempotency_key: str
    job_id: str
    request_fingerprint: str
    created_at: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def validate_idempotency_key(key: str) -> str:
    normalized = key.strip()
    reject_null_bytes(normalized, field_name="Idempotency-Key")
    if not normalized:
        raise ValueError("Idempotency-Key must be non-empty")
    if not _SAFE_IDEMPOTENCY_PATTERN.match(normalized):
        raise ValueError("Idempotency-Key is not a safe identifier")
    return normalized


class FileIdempotencyStore:
    """Filesystem-backed idempotency records scoped by principal."""

    def __init__(self, root: Path | str) -> None:
        self._root = Path(root).resolve()

    def _entry_path(self, principal_key_id: str, idempotency_key: str) -> Path:
        safe_principal = sanitize_request_id(principal_key_id)
        safe_key = validate_idempotency_key(idempotency_key)
        digest = hashlib.sha256(f"{safe_principal}:{safe_key}".encode("utf-8")).hexdigest()
        return self._root / safe_principal / f"{digest}.json"

    def get(self, *, principal_key_id: str, idempotency_key: str) -> IdempotencyEntry | None:
        path = self._entry_path(principal_key_id, idempotency_key)
        if not path.is_file():
            return None
        payload = json.loads(path.read_text(encoding="utf-8"))
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
        existing = self.get(
            principal_key_id=principal_key_id,
            idempotency_key=idempotency_key,
        )
        if existing is not None:
            if existing.request_fingerprint != request_fingerprint:
                raise IdempotencyConflictError("Idempotency key conflict")
            return existing
        entry = IdempotencyEntry(
            principal_key_id=principal_key_id,
            idempotency_key=idempotency_key,
            job_id=job_id,
            request_fingerprint=request_fingerprint,
            created_at=datetime.now(timezone.utc).isoformat(),
        )
        path = self._entry_path(principal_key_id, idempotency_key)
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(entry.to_dict(), indent=2), encoding="utf-8")
        os.replace(tmp, path)
        return entry


# Backward-compatible alias used by Stage 3.3 code paths.
IdempotencyStore = FileIdempotencyStore
