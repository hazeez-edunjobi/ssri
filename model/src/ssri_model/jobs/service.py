"""High-level job orchestration service."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import datetime, timezone
from typing import cast

from ssri_model.auth.models import AuthenticatedPrincipal, Role
from ssri_model.jobs.exceptions import (
    AsyncDisabledError,
    JobAccessDeniedError,
    JobNotFoundError,
)
from ssri_model.jobs.idempotency import IdempotencyEntry, validate_idempotency_key
from ssri_model.infrastructure.observability import log_operational_event
from ssri_model.jobs.models import JobRecord, JobStatus, JobType
from ssri_model.jobs.protocols import IdempotencyStoreProtocol, JobExecutorProtocol, JobStoreProtocol
from ssri_model.jobs.transitions import validate_transition

logger = logging.getLogger(__name__)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class JobService:
    """Create, access, and manage async jobs."""

    def __init__(
        self,
        store: JobStoreProtocol,
        executor: JobExecutorProtocol,
        idempotency_store: IdempotencyStoreProtocol,
        *,
        async_enabled: bool = True,
        max_attempts: int = 3,
    ) -> None:
        self._store = store
        self._executor = executor
        self._idempotency = idempotency_store
        self._async_enabled = async_enabled
        self._max_attempts = max_attempts

    def ensure_async_enabled(self) -> None:
        if not self._async_enabled:
            raise AsyncDisabledError("Async execution is disabled")

    def can_access(self, record: JobRecord, principal: AuthenticatedPrincipal) -> bool:
        if principal.role == Role.ADMIN:
            return True
        return record.submitted_by_key_id == principal.key_id

    def get_job(self, job_id: str, *, principal: AuthenticatedPrincipal) -> JobRecord:
        try:
            record = self._store.load(job_id)
        except JobNotFoundError:
            raise
        if not self.can_access(record, principal):
            raise JobAccessDeniedError("Job not found")
        return record

    def create_job(
        self,
        *,
        request_id: str,
        job_type: JobType,
        principal: AuthenticatedPrincipal,
        scientific_validation_status: str,
        payload: dict[str, object],
        idempotency_key: str | None = None,
    ) -> JobRecord:
        self.ensure_async_enabled()
        fingerprint = hashlib.sha256(
            json.dumps(payload, sort_keys=True).encode("utf-8")
        ).hexdigest()
        if idempotency_key is not None:
            existing = self.resolve_idempotent(
                principal=principal,
                idempotency_key=idempotency_key,
                request_fingerprint=fingerprint,
            )
            if existing is not None:
                return existing

        now = utc_now_iso()
        job_id = self._store.generate_job_id()
        record = JobRecord(
            job_id=job_id,
            request_id=request_id,
            job_type=job_type,
            status=JobStatus.QUEUED,
            created_at=now,
            queued_at=now,
            submitted_by_key_id=principal.key_id,
            auth_role=principal.role.value,
            scientific_validation_status=scientific_validation_status,
            idempotency_key=idempotency_key,
            payload=payload,
            max_attempts=self._max_attempts,
        )
        self._store.save(record)
        if idempotency_key is not None:
            self._idempotency.put(
                principal_key_id=principal.key_id,
                idempotency_key=validate_idempotency_key(idempotency_key),
                job_id=job_id,
                request_fingerprint=fingerprint,
            )
        logger.info(
            json.dumps(
                {
                    "event": "job_created",
                    "job_id": job_id,
                    "request_id": request_id,
                    "job_type": job_type.value,
                }
            )
        )
        log_operational_event(
            "job_submitted",
            job_id=job_id,
            request_id=request_id,
            job_type=job_type.value,
        )
        return record

    def resolve_idempotent(
        self,
        *,
        principal: AuthenticatedPrincipal,
        idempotency_key: str,
        request_fingerprint: str,
    ) -> JobRecord | None:
        entry = self._idempotency.get(
            principal_key_id=principal.key_id,
            idempotency_key=validate_idempotency_key(idempotency_key),
        )
        if entry is None:
            return None
        entry_obj = cast(IdempotencyEntry, entry)
        if entry_obj.request_fingerprint != request_fingerprint:
            from ssri_model.jobs.exceptions import IdempotencyConflictError

            raise IdempotencyConflictError("Idempotency key conflict")
        return self._store.load(entry_obj.job_id)

    def mark_completed(self, job_id: str, *, result: dict[str, object]) -> JobRecord:
        record = self._store.load(job_id)
        validate_transition(record.status, JobStatus.COMPLETED)
        if hasattr(self._store, "transition"):
            updated = cast(
                JobRecord,
                self._store.transition(
                    job_id,
                    target=JobStatus.COMPLETED,
                    expected=record.status,
                    updates={
                        "completed_at": utc_now_iso(),
                        "result": dict(result),
                    },
                ),
            )
            self._store.save_result(job_id, result)
            logger.info(json.dumps({"event": "job_completed", "job_id": job_id}))
            return updated
        record.status = JobStatus.COMPLETED
        record.completed_at = utc_now_iso()
        record.result = dict(result)
        self._store.save(record)
        self._store.save_result(job_id, result)
        logger.info(json.dumps({"event": "job_completed", "job_id": job_id}))
        return record

    def mark_failed(
        self,
        job_id: str,
        *,
        error_code: str,
        error_message: str,
    ) -> JobRecord:
        record = self._store.load(job_id)
        validate_transition(record.status, JobStatus.FAILED)
        now = utc_now_iso()
        if hasattr(self._store, "transition"):
            updated = cast(
                JobRecord,
                self._store.transition(
                    job_id,
                    target=JobStatus.FAILED,
                    expected=record.status,
                    updates={
                        "failed_at": now,
                        "completed_at": now,
                        "error_code": error_code,
                        "error_message": error_message,
                    },
                ),
            )
            logger.info(json.dumps({"event": "job_failed", "job_id": job_id}))
            return updated
        record.status = JobStatus.FAILED
        record.failed_at = now
        record.completed_at = now
        record.error_code = error_code
        record.error_message = error_message
        self._store.save(record)
        logger.info(json.dumps({"event": "job_failed", "job_id": job_id}))
        return record
