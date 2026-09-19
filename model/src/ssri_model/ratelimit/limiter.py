"""In-process sliding-window rate limiting."""

from __future__ import annotations

import threading
import time
from collections import defaultdict
from dataclasses import dataclass


@dataclass(frozen=True)
class RateLimitResult:
    allowed: bool
    retry_after_seconds: float


class RateLimiter:
    """Thread-safe sliding-window rate limiter keyed by client identifier."""

    def __init__(self, *, max_requests: int, window_seconds: float) -> None:
        if max_requests <= 0:
            raise ValueError("max_requests must be positive")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be positive")
        self._max_requests = max_requests
        self._window_seconds = window_seconds
        self._events: dict[str, list[float]] = defaultdict(list)
        self._lock = threading.Lock()

    def check(self, key: str, *, now: float | None = None) -> RateLimitResult:
        current = now if now is not None else time.monotonic()
        cutoff = current - self._window_seconds
        with self._lock:
            timestamps = [ts for ts in self._events[key] if ts > cutoff]
            if len(timestamps) >= self._max_requests:
                oldest = min(timestamps)
                retry_after = max(0.0, self._window_seconds - (current - oldest))
                self._events[key] = timestamps
                return RateLimitResult(allowed=False, retry_after_seconds=retry_after)
            timestamps.append(current)
            self._events[key] = timestamps
            return RateLimitResult(allowed=True, retry_after_seconds=0.0)

    def reset(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._events.clear()
            else:
                self._events.pop(key, None)
