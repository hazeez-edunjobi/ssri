"""Redis client helpers."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis


def create_redis_client(redis_url: str) -> redis.Redis:
    import redis

    return redis.Redis.from_url(redis_url, decode_responses=True)


def ping_redis(client: redis.Redis) -> bool:
    try:
        return bool(client.ping())
    except Exception:
        return False
