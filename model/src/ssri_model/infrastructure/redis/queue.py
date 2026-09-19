"""Redis-backed durable job queue."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import redis

_QUEUE_KEY = "ssri:job_queue"
_INFLIGHT_KEY = "ssri:job_inflight"


class RedisJobQueue:
    """Simple durable Redis list queue with in-flight tracking."""

    def __init__(self, client: redis.Redis) -> None:
        self._client = client

    def enqueue(self, job_id: str) -> None:
        self._client.rpush(_QUEUE_KEY, job_id)

    def dequeue(self) -> str | None:
        item = self._client.lpop(_QUEUE_KEY)
        if item is None:
            return None
        job_id = str(item)
        self._client.hset(_INFLIGHT_KEY, job_id, "1")
        return job_id

    def acknowledge(self, job_id: str) -> None:
        self._client.hdel(_INFLIGHT_KEY, job_id)

    def requeue(self, job_id: str) -> None:
        self._client.hdel(_INFLIGHT_KEY, job_id)
        self._client.lpush(_QUEUE_KEY, job_id)

    def inflight(self) -> list[str]:
        raw = list(self._client.hkeys(_INFLIGHT_KEY))  # type: ignore[arg-type]
        return [str(item) for item in raw]

    def depth(self) -> int:
        return int(self._client.llen(_QUEUE_KEY))  # type: ignore[arg-type]
