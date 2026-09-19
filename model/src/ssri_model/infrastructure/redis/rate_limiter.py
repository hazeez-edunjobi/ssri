"""Redis-backed distributed sliding-window rate limiter."""

from __future__ import annotations

import time
import uuid
from typing import TYPE_CHECKING, Any

from ssri_model.ratelimit import RateLimitResult

if TYPE_CHECKING:
    import redis

_KEY_PREFIX = "ssri:ratelimit"


class RedisRateLimiter:
    """Shared sliding-window limiter using Redis sorted sets."""

    def __init__(
        self,
        client: redis.Redis,
        *,
        max_requests: int,
        window_seconds: float,
        bucket: str = "default",
    ) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._client = client
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._bucket = bucket

    def _key(self, client_key: str) -> str:
        return f"{_KEY_PREFIX}:{self._bucket}:{client_key}"

    def check(self, key: str, *, now: float | None = None) -> RateLimitResult:
        current = now if now is not None else time.time()
        window_start = current - self._window_seconds
        redis_key = self._key(key)
        member = f"{current}:{uuid.uuid4().hex}"
        pipe = self._client.pipeline()
        pipe.zremrangebyscore(redis_key, 0, window_start)
        pipe.zadd(redis_key, {member: current})
        pipe.zcard(redis_key)
        pipe.expire(redis_key, int(self._window_seconds) + 1)
        results: list[Any] = list(pipe.execute())
        count_int = int(results[2])
        if count_int > self._max_requests:
            oldest_raw: list[tuple[str, float]] = list(
                self._client.zrange(redis_key, 0, 0, withscores=True)  # type: ignore[arg-type]
            )
            retry_after = self._window_seconds
            if oldest_raw:
                oldest_pair = oldest_raw[0]
                retry_after = max(
                    0.0,
                    self._window_seconds - (current - float(oldest_pair[1])),
                )
            self._client.zrem(redis_key, member)
            return RateLimitResult(allowed=False, retry_after_seconds=retry_after)
        return RateLimitResult(allowed=True, retry_after_seconds=0.0)

    def reset(self, key: str | None = None) -> None:
        if key is None:
            pattern = f"{_KEY_PREFIX}:{self._bucket}:*"
            for match in self._client.scan_iter(match=pattern):
                self._client.delete(match)
            return
        self._client.delete(self._key(key))
