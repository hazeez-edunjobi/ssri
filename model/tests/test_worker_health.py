"""Worker health probe unit tests."""

from __future__ import annotations

from types import SimpleNamespace

import pytest


def test_worker_concurrency_defaults_to_one(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSRI_CELERY_CONCURRENCY", raising=False)
    from ssri_model.worker.celery_app import worker_concurrency

    assert worker_concurrency() == 1


def test_worker_concurrency_reads_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_CELERY_CONCURRENCY", "2")
    from ssri_model.worker.celery_app import worker_concurrency

    assert worker_concurrency() == 2


def test_worker_concurrency_rejects_invalid(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_CELERY_CONCURRENCY", "0")
    from ssri_model.worker.celery_app import worker_concurrency

    with pytest.raises(RuntimeError):
        worker_concurrency()


def test_worker_health_fails_without_broker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SSRI_CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("CELERY_BROKER_URL", raising=False)
    monkeypatch.delenv("SSRI_REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    from ssri_model.worker.health import check_worker_health

    assert check_worker_health() == 1


def test_worker_health_ok_with_reachable_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SSRI_REDIS_URL", "redis://localhost:6379/0")

    class FakeRedis:
        def ping(self):
            return True

    import redis as redis_mod

    monkeypatch.setattr(
        redis_mod.Redis,
        "from_url",
        staticmethod(lambda *_a, **_k: FakeRedis()),
    )
    monkeypatch.setattr(
        "ssri_model.worker.celery_app.celery_app",
        SimpleNamespace(main="ssri"),
        raising=False,
    )
    # Ensure import path used inside health check succeeds.
    import ssri_model.worker.health as health_mod

    class FakeAppModule:
        celery_app = SimpleNamespace(main="ssri")

    monkeypatch.setitem(
        __import__("sys").modules,
        "ssri_model.worker.celery_app",
        FakeAppModule(),
    )
    assert health_mod.check_worker_health() == 0
