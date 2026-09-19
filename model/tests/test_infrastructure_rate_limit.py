"""Tests for Redis-backed distributed rate limiting."""

from __future__ import annotations

from tests.infrastructure_helpers import build_fakeredis_client, build_redis_rate_limiter


def test_redis_rate_limiter_enforces_limit() -> None:
    client = build_fakeredis_client()
    limiter_a = build_redis_rate_limiter(max_requests=2, window_seconds=60.0)
    limiter_b = build_redis_rate_limiter(max_requests=2, window_seconds=60.0)
    limiter_b._client = client
    limiter_a._client = client
    assert limiter_a.check("client-1", now=100.0).allowed is True
    assert limiter_a.check("client-1", now=101.0).allowed is True
    blocked = limiter_a.check("client-1", now=102.0)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds >= 0


def test_redis_rate_limiter_shared_across_instances() -> None:
    client = build_fakeredis_client()
    first = build_redis_rate_limiter(max_requests=1, window_seconds=60.0)
    second = build_redis_rate_limiter(max_requests=1, window_seconds=60.0)
    first._client = client
    second._client = client
    assert first.check("shared-client", now=1.0).allowed is True
    assert second.check("shared-client", now=2.0).allowed is False
