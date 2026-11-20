"""Redis client helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis


def create_redis_client(redis_url: str) -> redis.Redis:
    import redis

    # socket_connect_timeout / socket_timeout keep readiness probes bounded.
    return redis.Redis.from_url(
        redis_url,
        decode_responses=True,
        socket_connect_timeout=5,
        socket_timeout=5,
    )


def ping_redis(client: redis.Redis) -> bool:
    """Return True when PING succeeds. Exceptions are swallowed for boolean callers."""
    ok, _reason = ping_redis_with_reason(client)
    return ok


def ping_redis_with_reason(client: redis.Redis) -> tuple[bool, str]:
    """PING Redis and return (ok, detail) without including connection secrets."""
    try:
        if bool(client.ping()):
            return True, "connected"
        return False, "ping_failed"
    except Exception as exc:
        # Exception type only — never stringify the URL or credentials.
        return False, f"ping_failed:{type(exc).__name__}"
