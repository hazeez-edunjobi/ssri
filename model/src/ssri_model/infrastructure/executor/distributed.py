"""Distributed job executor using Celery and Redis."""

from __future__ import annotations

import json
import logging

from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.redis.queue import RedisJobQueue
from ssri_model.jobs.exceptions import JobCannotCancelError, JobQueueFullError
from ssri_model.jobs.models import JobRecord, JobStatus

logger = logging.getLogger(__name__)


class DistributedJobExecutor:
    """Enqueue durable jobs for external worker processes."""

    def __init__(
        self,
        store: DatabaseJobStore,
        queue: RedisJobQueue,
        *,
        max_queue_size: int,
        celery_task_name: str,
    ) -> None:
        self._store = store
        self._queue = queue
        self._max_queue_size = max_queue_size
        self._celery_task_name = celery_task_name

    @property
    def queued_count(self) -> int:
        return self._queue.depth() + len(self._queue.inflight())

    def submit(self, job_id: str, worker: object | None = None) -> None:
        if self.queued_count >= self._max_queue_size:
            raise JobQueueFullError("Job queue is full")
        record = self._store.load(job_id)
        if record.status != JobStatus.QUEUED:
            raise JobCannotCancelError("Job is not queued")
        if record.cancel_requested:
            self._store.transition(
                job_id,
                target=JobStatus.CANCELLED,
                expected=JobStatus.QUEUED,
            )
            return
        self._queue.enqueue(job_id)
        from ssri_model.worker.celery_app import get_celery_app

        get_celery_app().send_task(self._celery_task_name, args=[job_id])
        logger.info(json.dumps({"event": "job_enqueued", "job_id": job_id}))

    def get_status(self, job_id: str) -> JobRecord:
        return self._store.load(job_id)

    def cancel(self, job_id: str) -> JobRecord:
        record = self._store.load(job_id)
        if record.status in {JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED}:
            raise JobCannotCancelError("Job cannot be cancelled")
        if record.status == JobStatus.QUEUED:
            return self._store.transition(
                job_id,
                target=JobStatus.CANCELLED,
                expected=JobStatus.QUEUED,
                updates={"cancel_requested": True},
            )
        record.cancel_requested = True
        self._store.save(record)
        return self._store.load(job_id)

    def shutdown(self, *, wait: bool = False) -> None:
        _ = wait
