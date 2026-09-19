"""Rate limit enforcement helpers."""

from __future__ import annotations

import json
import logging


from ssri_model.ratelimit import RateLimiter

logger = logging.getLogger(__name__)


class RateLimitExceeded(Exception):
    """Raised when a client exceeds configured rate limits."""

    def __init__(self, *, retry_after_seconds: float) -> None:
        self.retry_after_seconds = retry_after_seconds
        super().__init__("Rate limit exceeded.")


def enforce_rate_limit(limiter: RateLimiter, key: str) -> None:
    result = limiter.check(key)
    if not result.allowed:
        logger.info(
            json.dumps(
                {
                    "event": "rate_limit_exceeded",
                    "client_key": key,
                    "retry_after_seconds": result.retry_after_seconds,
                }
            )
        )
        raise RateLimitExceeded(retry_after_seconds=result.retry_after_seconds)
