import os
from dataclasses import dataclass
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class WorkerSettings:
    """Worker settings loaded from environment variables."""

    worker_name: str = "ssri-worker"
    log_level: str = "INFO"
    broker_url: str = "redis://localhost:6379/0"
    result_backend: str = "redis://localhost:6379/0"

    @classmethod
    def from_env(cls) -> "WorkerSettings":
        broker_url = os.getenv("CELERY_BROKER_URL") or os.getenv(
            "REDIS_URL", "redis://localhost:6379/0"
        )
        result_backend = os.getenv("CELERY_RESULT_BACKEND", broker_url)
        return cls(
            worker_name=os.getenv("WORKER_NAME", "ssri-worker"),
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            broker_url=broker_url,
            result_backend=result_backend,
        )


@lru_cache
def get_settings() -> WorkerSettings:
    """Return cached worker settings."""
    return WorkerSettings.from_env()
