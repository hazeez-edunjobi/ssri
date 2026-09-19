"""Job domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any, Mapping


class JobStatus(str, Enum):
    QUEUED = "queued"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class JobType(str, Enum):
    INFERENCE = "inference"
    BATCH = "batch"


@dataclass
class JobRecord:
    """Durable job metadata."""

    job_id: str
    request_id: str
    job_type: JobType
    status: JobStatus
    created_at: str
    submitted_by_key_id: str
    auth_role: str
    scientific_validation_status: str = "NOT_VALIDATED"
    idempotency_key: str | None = None
    queued_at: str | None = None
    started_at: str | None = None
    completed_at: str | None = None
    failed_at: str | None = None
    output_dir: str | None = None
    output_location: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    payload: dict[str, Any] = field(default_factory=dict)
    result: dict[str, Any] = field(default_factory=dict)
    cancel_requested: bool = False
    worker_id: str | None = None
    attempt: int = 0
    max_attempts: int = 3
    heartbeat_at: str | None = None
    version: int = 1
    recovery_count: int = 0
    last_recovery_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["job_type"] = self.job_type.value
        payload["status"] = self.status.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> JobRecord:
        return cls(
            job_id=str(payload["job_id"]),
            request_id=str(payload["request_id"]),
            job_type=JobType(str(payload["job_type"])),
            status=JobStatus(str(payload["status"])),
            created_at=str(payload["created_at"]),
            submitted_by_key_id=str(payload["submitted_by_key_id"]),
            auth_role=str(payload["auth_role"]),
            scientific_validation_status=str(
                payload.get("scientific_validation_status", "NOT_VALIDATED")
            ),
            idempotency_key=payload.get("idempotency_key"),
            queued_at=payload.get("queued_at"),
            started_at=payload.get("started_at"),
            completed_at=payload.get("completed_at"),
            failed_at=payload.get("failed_at"),
            output_dir=payload.get("output_dir"),
            output_location=payload.get("output_location"),
            error_code=payload.get("error_code"),
            error_message=payload.get("error_message"),
            payload=dict(payload.get("payload", {})),
            result=dict(payload.get("result") or {}),
            cancel_requested=bool(payload.get("cancel_requested", False)),
            worker_id=payload.get("worker_id"),
            attempt=int(payload.get("attempt", 0)),
            max_attempts=int(payload.get("max_attempts", 3)),
            heartbeat_at=payload.get("heartbeat_at"),
            version=int(payload.get("version", 1)),
            recovery_count=int(payload.get("recovery_count", 0)),
            last_recovery_at=payload.get("last_recovery_at"),
        )
