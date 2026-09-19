"""Tests for Stage 3.3 rate limiting."""

from __future__ import annotations

import threading

from ssri_model.ratelimit import RateLimiter
from tests.api_helpers import build_inference_fixture, build_inference_payload
from tests.auth_helpers import auth_header
from tests.operational_helpers import build_operational_api_config, create_operational_client


def test_rate_limiter_enforces_window() -> None:
    limiter = RateLimiter(max_requests=2, window_seconds=10.0)
    assert limiter.check("client-a", now=100.0).allowed is True
    assert limiter.check("client-a", now=101.0).allowed is True
    blocked = limiter.check("client-a", now=102.0)
    assert blocked.allowed is False
    assert blocked.retry_after_seconds > 0


def test_rate_limiter_isolates_keys() -> None:
    limiter = RateLimiter(max_requests=1, window_seconds=10.0)
    assert limiter.check("client-a", now=1.0).allowed is True
    assert limiter.check("client-b", now=1.0).allowed is True
    assert limiter.check("client-a", now=2.0).allowed is False


def test_rate_limiter_thread_safe() -> None:
    limiter = RateLimiter(max_requests=50, window_seconds=60.0)
    allowed: list[bool] = []

    def worker(key: str) -> None:
        for _ in range(20):
            allowed.append(limiter.check(key).allowed)

    threads = [threading.Thread(target=worker, args=(f"key-{idx}",)) for idx in range(4)]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()
    assert len(allowed) == 80
    assert all(allowed)


def test_inference_rate_limit_returns_429_with_retry_after(tmp_path) -> None:
    config, keys = build_operational_api_config(
        tmp_path,
        rate_limit_enabled=True,
        inference_requests_per_window=1,
    )
    client = create_operational_client(tmp_path, api_config=config)
    operator_key, _ = keys["operator"]
    headers = auth_header(operator_key)
    feature, manifest, statistics, checkpoint = build_inference_fixture(tmp_path)

    payload = build_inference_payload(
        request_id="rate-limit-1",
        feature=feature,
        manifest=manifest,
        statistics=statistics,
        checkpoint=checkpoint,
    )
    first = client.post("/api/v1/inference/async", json=payload, headers=headers)
    assert first.status_code == 202

    payload["request_id"] = "rate-limit-2"
    second = client.post("/api/v1/inference/async", json=payload, headers=headers)
    assert second.status_code == 429
    body = second.json()
    assert body["error"]["code"] == "RATE_LIMIT_EXCEEDED"
    assert "retry_after_seconds" in body["error"]["details"]
    assert second.headers.get("Retry-After")


def test_health_endpoints_not_rate_limited(tmp_path) -> None:
    config, _ = build_operational_api_config(tmp_path, rate_limit_enabled=True)
    client = create_operational_client(tmp_path, api_config=config)
    for _ in range(5):
        assert client.get("/health").status_code == 200
        assert client.get("/api/v1/health").status_code == 200
