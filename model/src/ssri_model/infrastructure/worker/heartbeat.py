"""Worker heartbeat maintenance during job execution."""

from __future__ import annotations

import threading
from collections.abc import Callable

from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.observability import log_operational_event
from ssri_model.jobs.models import JobStatus
from ssri_model.jobs.service import utc_now_iso


class HeartbeatController:
    """Periodically refresh a running job heartbeat until stopped."""

    def __init__(
        self,
        store: DatabaseJobStore,
        *,
        job_id: str,
        worker_id: str,
        interval_seconds: float,
        should_continue: Callable[[], bool] | None = None,
    ) -> None:
        self._store = store
        self._job_id = job_id
        self._worker_id = worker_id
        self._interval_seconds = interval_seconds
        self._should_continue = should_continue or (lambda: True)
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._expected_heartbeat: str | None = None
        self._expected_version = 0

    def start(self, *, initial_heartbeat: str, initial_version: int) -> None:
        self._expected_heartbeat = initial_heartbeat
        self._expected_version = initial_version
        self._thread = threading.Thread(
            target=self._run,
            name=f"ssri-heartbeat-{self._job_id}",
            daemon=True,
        )
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=self._interval_seconds + 1)

    def _run(self) -> None:
        while not self._stop.is_set() and self._should_continue():
            if self._stop.wait(timeout=self._interval_seconds):
                break
            if not self._should_continue():
                break
            record = self._store.load(self._job_id)
            if record.status != JobStatus.RUNNING:
                break
            if record.worker_id != self._worker_id:
                break
            new_heartbeat = utc_now_iso()
            updated = self._store.update_heartbeat(
                self._job_id,
                worker_id=self._worker_id,
                heartbeat_at=new_heartbeat,
                expected_heartbeat_at=self._expected_heartbeat,
                expected_version=self._expected_version,
            )
            if not updated:
                log_operational_event(
                    "heartbeat_failed",
                    job_id=self._job_id,
                    worker_id=self._worker_id,
                )
                break
            self._expected_heartbeat = new_heartbeat
            self._expected_version += 1
