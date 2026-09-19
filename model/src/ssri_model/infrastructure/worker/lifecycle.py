"""Worker lifecycle helpers."""

from __future__ import annotations

import threading

from ssri_model.infrastructure.observability import log_operational_event

_shutdown = threading.Event()


def request_worker_shutdown() -> None:
    _shutdown.set()
    log_operational_event("worker_shutdown")


def worker_shutdown_requested() -> bool:
    return _shutdown.is_set()


def reset_worker_shutdown() -> None:
    _shutdown.clear()
