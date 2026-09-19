"""Structured authentication audit logging."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger("ssri.auth.audit")


@dataclass(frozen=True)
class AuthenticationAuditRecord:
    """Structured audit metadata for authentication events."""

    event: str
    request_id: str | None
    key_id: str | None
    role: str | None
    endpoint: str
    method: str
    timestamp: str
    outcome: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def log_authentication_event(
    *,
    request_id: str | None,
    key_id: str | None,
    role: str | None,
    endpoint: str,
    method: str,
    outcome: str,
) -> AuthenticationAuditRecord:
    record = AuthenticationAuditRecord(
        event="authentication",
        request_id=request_id,
        key_id=key_id,
        role=role,
        endpoint=endpoint,
        method=method,
        timestamp=utc_now_iso(),
        outcome=outcome,
    )
    logger.info(json.dumps(record.to_dict(), sort_keys=True))
    return record


def log_auth_management_event(
    *,
    event: str,
    key_id: str | None,
    actor_key_id: str | None,
    role: str | None,
    outcome: str,
) -> AuthenticationAuditRecord:
    record = AuthenticationAuditRecord(
        event=event,
        request_id=None,
        key_id=key_id,
        role=role,
        endpoint="auth/key-management",
        method="INTERNAL",
        timestamp=utc_now_iso(),
        outcome=outcome,
    )
    payload = record.to_dict()
    payload["actor_key_id"] = actor_key_id
    logger.info(json.dumps(payload, sort_keys=True))
    return record
