"""Database-backed durable job store."""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy import select, update
from sqlalchemy.engine import Engine
from sqlalchemy.exc import IntegrityError

from ssri_model.infrastructure.database.schema import init_schema, jobs_table
from ssri_model.jobs.exceptions import InvalidJobTransitionError, JobNotFoundError
from ssri_model.jobs.models import JobRecord, JobStatus
from ssri_model.jobs.transitions import validate_transition
from ssri_model.service.validation import reject_path_traversal, sanitize_request_id


def _row_to_record(row: dict[str, Any]) -> JobRecord:
    return JobRecord.from_dict(row)


def _record_to_row(record: JobRecord) -> dict[str, Any]:
    return {
        "job_id": record.job_id,
        "request_id": record.request_id,
        "job_type": record.job_type.value,
        "status": record.status.value,
        "submitted_by_key_id": record.submitted_by_key_id,
        "auth_role": record.auth_role,
        "scientific_validation_status": record.scientific_validation_status,
        "idempotency_key": record.idempotency_key,
        "payload": record.payload,
        "result": record.result or None,
        "created_at": record.created_at,
        "queued_at": record.queued_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "failed_at": record.failed_at,
        "cancel_requested": record.cancel_requested,
        "error_code": record.error_code,
        "error_message": record.error_message,
        "output_dir": record.output_dir,
        "output_location": record.output_location,
        "worker_id": record.worker_id,
        "attempt": record.attempt,
        "max_attempts": record.max_attempts,
        "heartbeat_at": record.heartbeat_at,
        "version": record.version,
        "recovery_count": record.recovery_count,
        "last_recovery_at": record.last_recovery_at,
    }


class DatabaseJobStore:
    """PostgreSQL/SQLite-backed job store with transactional state transitions."""

    def __init__(self, engine: Engine, *, auto_init: bool = True) -> None:
        self._engine = engine
        if auto_init:
            init_schema(engine)

    @property
    def engine(self) -> Engine:
        return self._engine

    def close(self) -> None:
        self._engine.dispose()

    def save(self, record: JobRecord) -> None:
        reject_path_traversal(record.job_id, field_name="job_id")
        row = _record_to_row(record)
        try:
            with self._engine.begin() as conn:
                conn.execute(jobs_table.insert().values(**row))
        except IntegrityError:
            current = self.load(record.job_id)
            if current.status != record.status:
                validate_transition(current.status, record.status)
            row["version"] = current.version + 1
            with self._engine.begin() as conn:
                result = conn.execute(
                    update(jobs_table)
                    .where(
                        jobs_table.c.job_id == record.job_id,
                        jobs_table.c.version == current.version,
                    )
                    .values(**row)
                )
                if result.rowcount != 1:
                    raise InvalidJobTransitionError(
                        f"Concurrent update conflict for job {record.job_id}"
                    )

    def load(self, job_id: str) -> JobRecord:
        safe_id = sanitize_request_id(job_id)
        with self._engine.connect() as conn:
            return self._load_conn(conn, safe_id)

    def _load_conn(self, conn: Any, job_id: str) -> JobRecord:
        row = conn.execute(
            select(jobs_table).where(jobs_table.c.job_id == job_id)
        ).mappings().first()
        if row is None:
            raise JobNotFoundError("Job not found")
        return _row_to_record(dict(row))

    def transition(
        self,
        job_id: str,
        *,
        target: JobStatus,
        expected: JobStatus,
        updates: dict[str, Any] | None = None,
    ) -> JobRecord:
        record = self.load(job_id)
        validate_transition(record.status, target)
        if record.status != expected:
            raise InvalidJobTransitionError(
                f"Expected status {expected.value}, found {record.status.value}"
            )
        next_version = record.version + 1
        values: dict[str, Any] = {
            "status": target.value,
            "version": next_version,
        }
        if updates:
            values.update(updates)
        with self._engine.begin() as conn:
            result = conn.execute(
                update(jobs_table)
                .where(
                    jobs_table.c.job_id == job_id,
                    jobs_table.c.status == expected.value,
                    jobs_table.c.version == record.version,
                )
                .values(**values)
            )
            if result.rowcount != 1:
                raise InvalidJobTransitionError(
                    f"Concurrent transition conflict for job {job_id}"
                )
        return self.load(job_id)

    def claim(
        self,
        job_id: str,
        *,
        worker_id: str,
        started_at: str,
        heartbeat_at: str,
    ) -> JobRecord | None:
        record = self.load(job_id)
        if record.cancel_requested and record.status == JobStatus.QUEUED:
            self.transition(
                job_id,
                target=JobStatus.CANCELLED,
                expected=JobStatus.QUEUED,
            )
            return self.load(job_id)
        if record.status != JobStatus.QUEUED:
            return None
        attempt = record.attempt + 1
        with self._engine.begin() as conn:
            result = conn.execute(
                update(jobs_table)
                .where(
                    jobs_table.c.job_id == job_id,
                    jobs_table.c.status == JobStatus.QUEUED.value,
                    jobs_table.c.cancel_requested.is_(False),
                    jobs_table.c.version == record.version,
                )
                .values(
                    status=JobStatus.RUNNING.value,
                    worker_id=worker_id,
                    started_at=started_at,
                    heartbeat_at=heartbeat_at,
                    attempt=attempt,
                    version=record.version + 1,
                )
            )
            if result.rowcount != 1:
                return None
        return self.load(job_id)

    def save_result(self, job_id: str, result: dict[str, object]) -> None:
        with self._engine.begin() as conn:
            conn.execute(
                update(jobs_table)
                .where(jobs_table.c.job_id == job_id)
                .values(result=dict(result))
            )

    def load_result(self, job_id: str) -> dict[str, object]:
        record = self.load(job_id)
        return dict(record.result)

    def update_heartbeat(
        self,
        job_id: str,
        *,
        worker_id: str,
        heartbeat_at: str,
        expected_heartbeat_at: str | None,
        expected_version: int,
    ) -> bool:
        conditions = [
            jobs_table.c.job_id == job_id,
            jobs_table.c.worker_id == worker_id,
            jobs_table.c.status == JobStatus.RUNNING.value,
            jobs_table.c.version == expected_version,
        ]
        if expected_heartbeat_at is not None:
            conditions.append(jobs_table.c.heartbeat_at == expected_heartbeat_at)
        with self._engine.begin() as conn:
            result = conn.execute(
                update(jobs_table)
                .where(*conditions)
                .values(
                    heartbeat_at=heartbeat_at,
                    version=expected_version + 1,
                )
            )
            return result.rowcount == 1

    def list_stale_running_jobs(
        self,
        *,
        heartbeat_cutoff: str,
        limit: int,
    ) -> list[JobRecord]:
        with self._engine.connect() as conn:
            rows = conn.execute(
                select(jobs_table)
                .where(
                    jobs_table.c.status == JobStatus.RUNNING.value,
                    jobs_table.c.heartbeat_at.is_not(None),
                    jobs_table.c.heartbeat_at < heartbeat_cutoff,
                )
                .order_by(jobs_table.c.heartbeat_at.asc())
                .limit(limit)
            ).mappings()
            return [_row_to_record(dict(row)) for row in rows]

    def recover_stale_job(
        self,
        job_id: str,
        *,
        heartbeat_cutoff: str,
        recovered_at: str,
    ) -> JobRecord | None:
        try:
            record = self.load(job_id)
        except JobNotFoundError:
            return None
        if record.status != JobStatus.RUNNING:
            return None
        if record.heartbeat_at is None or record.heartbeat_at >= heartbeat_cutoff:
            return None
        if record.attempt >= record.max_attempts:
            try:
                return self.transition(
                    job_id,
                    target=JobStatus.FAILED,
                    expected=JobStatus.RUNNING,
                    updates={
                        "failed_at": recovered_at,
                        "completed_at": recovered_at,
                        "error_code": "LEASE_EXPIRED",
                        "error_message": "Worker lease expired before job completion.",
                        "worker_id": None,
                        "heartbeat_at": None,
                    },
                )
            except InvalidJobTransitionError:
                return None
        try:
            return self.transition(
                job_id,
                target=JobStatus.QUEUED,
                expected=JobStatus.RUNNING,
                updates={
                    "queued_at": recovered_at,
                    "started_at": None,
                    "worker_id": None,
                    "heartbeat_at": None,
                    "error_code": "STALE_LEASE_RECOVERED",
                    "error_message": "Job requeued after stale worker lease.",
                    "recovery_count": record.recovery_count + 1,
                    "last_recovery_at": recovered_at,
                },
            )
        except InvalidJobTransitionError:
            return None

    @staticmethod
    def generate_job_id() -> str:
        return f"job-{secrets.token_hex(8)}"
