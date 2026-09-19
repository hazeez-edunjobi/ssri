"""Thread-pool based job executor."""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor

from ssri_model.jobs.exceptions import JobCannotCancelError, JobQueueFullError
from ssri_model.jobs.models import JobRecord, JobStatus
from ssri_model.jobs.store import FileJobStore, JobStore

logger = logging.getLogger(__name__)


class LocalJobExecutor:
    """Submit background work using a replaceable thread pool."""

    def __init__(
        self,
        store: FileJobStore | JobStore,
        *,
        max_workers: int = 2,
        max_queue_size: int = 100,
    ) -> None:
        self._store = store
        self._max_queue_size = max_queue_size
        self._lock = threading.RLock()
        self._futures: dict[str, Future[None]] = {}
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="ssri-job")

    @property
    def queued_count(self) -> int:
        with self._lock:
            return sum(
                1
                for job_id in self._futures
                if self._store.load(job_id).status in {JobStatus.QUEUED, JobStatus.RUNNING}
            )

    def submit(self, job_id: str, worker: Callable[[], None] | None = None) -> None:
        if worker is None:
            raise ValueError("LocalJobExecutor requires a worker callable")
        with self._lock:
            if self.queued_count >= self._max_queue_size:
                raise JobQueueFullError("Job queue is full")
            record = self._store.load(job_id)
            if record.status != JobStatus.QUEUED:
                raise JobCannotCancelError("Job is not queued")
            if record.cancel_requested:
                record.status = JobStatus.CANCELLED
                self._store.save(record)
                return

            def _run() -> None:
                current = self._store.load(job_id)
                if current.cancel_requested:
                    current.status = JobStatus.CANCELLED
                    self._store.save(current)
                    return
                current.status = JobStatus.RUNNING
                if current.started_at is None:
                    from ssri_model.jobs.service import utc_now_iso

                    current.started_at = utc_now_iso()
                self._store.save(current)
                try:
                    worker()
                except Exception:
                    logger.exception("Job %s failed", job_id)
                    failed = self._store.load(job_id)
                    if failed.status in {
                        JobStatus.COMPLETED,
                        JobStatus.FAILED,
                        JobStatus.CANCELLED,
                    }:
                        return
                    failed.status = JobStatus.FAILED
                    failed.error_code = "JOB_EXECUTION_FAILED"
                    failed.error_message = "Job execution failed."
                    self._store.save(failed)

            future = self._executor.submit(_run)
            self._futures[job_id] = future

    def get_status(self, job_id: str) -> JobRecord:
        return self._store.load(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        record = self._store.load(job_id)
        if record.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise JobCannotCancelError("Job cannot be cancelled")
        record.cancel_requested = True
        if record.status == JobStatus.QUEUED:
            record.status = JobStatus.CANCELLED
        self._store.save(record)
        return record

    def shutdown(self, *, wait: bool = False) -> None:
        self._executor.shutdown(wait=wait, cancel_futures=False)


# Backward-compatible alias used by Stage 3.3 code paths.
JobExecutor = LocalJobExecutor
