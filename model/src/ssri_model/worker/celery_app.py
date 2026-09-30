"""Celery application for distributed SSRI workers."""

from __future__ import annotations

import os
from functools import lru_cache

from celery import Celery


def worker_concurrency() -> int:
    """Prefork process count. Celery otherwise uses the host CPU count."""
    raw = os.getenv("SSRI_CELERY_CONCURRENCY", "1").strip()
    try:
        value = int(raw)
    except ValueError as exc:
        raise RuntimeError("SSRI_CELERY_CONCURRENCY must be a positive integer") from exc
    if value < 1:
        raise RuntimeError("SSRI_CELERY_CONCURRENCY must be a positive integer")
    return value


@lru_cache(maxsize=1)
def get_celery_app() -> Celery:
    broker = os.getenv("SSRI_CELERY_BROKER_URL") or os.getenv("SSRI_REDIS_URL", "redis://localhost:6379/0")
    backend = os.getenv("SSRI_CELERY_RESULT_BACKEND") or broker
    app = Celery("ssri", broker=broker, backend=backend)
    app.conf.update(
        task_serializer="json",
        accept_content=["json"],
        result_serializer="json",
        task_acks_late=True,
        task_reject_on_worker_lost=True,
        worker_prefetch_multiplier=1,
        worker_concurrency=worker_concurrency(),
        task_default_queue="ssri_jobs",
    )
    app.autodiscover_tasks(["ssri_model.worker"])
    return app


celery_app = get_celery_app()

# Import after app construction so task decorators register on the cached app.
import ssri_model.worker.tasks as _worker_tasks  # noqa: E402, F401