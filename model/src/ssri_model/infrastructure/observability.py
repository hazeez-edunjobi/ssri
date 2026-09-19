"""Structured operational event logging."""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("ssri.operations")

_SENSITIVE_KEYS = frozenset(
    {
        "api_key",
        "authorization",
        "password",
        "secret",
        "token",
        "database_url",
        "redis_url",
        "payload",
    }
)


def log_operational_event(event: str, **fields: Any) -> None:
    """Emit a sanitized structured operational event."""
    payload: dict[str, Any] = {"event": event}
    for key, value in fields.items():
        if key.lower() in _SENSITIVE_KEYS:
            continue
        if value is not None:
            payload[key] = value
    logger.info(json.dumps(payload))
