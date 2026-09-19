"""Operational configuration for Stage 3.3 features."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ssri_model.service.exceptions import InvalidServiceConfigError
from ssri_model.service.validation import reject_path_traversal


@dataclass(frozen=True)
class OperationalConfig:
    """Configuration for async jobs and rate limiting."""

    async_enabled: bool = True
    worker_count: int = 2
    max_queue_size: int = 100
    job_store_root: str = "jobs"
    rate_limit_enabled: bool = False
    inference_requests_per_window: int = 60
    inference_window_seconds: float = 60.0
    batch_requests_per_window: int = 30
    batch_window_seconds: float = 60.0
    status_requests_per_window: int = 120
    status_window_seconds: float = 60.0
    idempotency_ttl_seconds: int = 86_400

    def __post_init__(self) -> None:
        if self.worker_count < 1:
            raise InvalidServiceConfigError("worker_count must be at least 1")
        if self.max_queue_size < 1:
            raise InvalidServiceConfigError("max_queue_size must be at least 1")
        if not self.job_store_root.strip():
            raise InvalidServiceConfigError("job_store_root must be non-empty")
        reject_path_traversal(self.job_store_root, field_name="job_store_root")
        if self.inference_requests_per_window <= 0:
            raise InvalidServiceConfigError("inference_requests_per_window must be positive")
        if self.batch_requests_per_window <= 0:
            raise InvalidServiceConfigError("batch_requests_per_window must be positive")
        if self.status_requests_per_window <= 0:
            raise InvalidServiceConfigError("status_requests_per_window must be positive")
        if self.inference_window_seconds <= 0:
            raise InvalidServiceConfigError("inference_window_seconds must be positive")
        if self.batch_window_seconds <= 0:
            raise InvalidServiceConfigError("batch_window_seconds must be positive")
        if self.status_window_seconds <= 0:
            raise InvalidServiceConfigError("status_window_seconds must be positive")
        if self.idempotency_ttl_seconds <= 0:
            raise InvalidServiceConfigError("idempotency_ttl_seconds must be positive")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> OperationalConfig:
        return cls(
            async_enabled=bool(payload.get("async_enabled", True)),
            worker_count=int(payload.get("worker_count", 2)),
            max_queue_size=int(payload.get("max_queue_size", 100)),
            job_store_root=str(payload.get("job_store_root", "jobs")),
            rate_limit_enabled=bool(payload.get("rate_limit_enabled", False)),
            inference_requests_per_window=int(
                payload.get("inference_requests_per_window", 60)
            ),
            inference_window_seconds=float(payload.get("inference_window_seconds", 60.0)),
            batch_requests_per_window=int(payload.get("batch_requests_per_window", 30)),
            batch_window_seconds=float(payload.get("batch_window_seconds", 60.0)),
            status_requests_per_window=int(payload.get("status_requests_per_window", 120)),
            status_window_seconds=float(payload.get("status_window_seconds", 60.0)),
            idempotency_ttl_seconds=int(payload.get("idempotency_ttl_seconds", 86_400)),
        )
