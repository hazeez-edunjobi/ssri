"""Worker process health probe for Docker/Compose.

Distinguishes:
- process can import Celery app
- broker (Redis) is reachable

Exit codes:
  0 = healthy enough to accept work
  1 = unhealthy
"""

from __future__ import annotations

import os
import sys


def check_worker_health() -> int:
    broker = (
        os.getenv("SSRI_CELERY_BROKER_URL")
        or os.getenv("CELERY_BROKER_URL")
        or os.getenv("SSRI_REDIS_URL")
        or os.getenv("REDIS_URL")
    )
    if not broker:
        print("worker_health: missing broker URL", file=sys.stderr)
        return 1

    try:
        from redis import Redis

        client = Redis.from_url(broker, socket_connect_timeout=2, socket_timeout=2)
        if client.ping() is not True:
            print("worker_health: redis ping failed", file=sys.stderr)
            return 1
    except Exception as exc:  # pragma: no cover - exercised in runtime
        print(f"worker_health: broker unreachable ({type(exc).__name__})", file=sys.stderr)
        return 1

    try:
        from ssri_model.worker.celery_app import celery_app

        _ = celery_app.main
    except Exception as exc:  # pragma: no cover
        print(
            f"worker_health: celery app import failed ({type(exc).__name__}: {exc})",
            file=sys.stderr,
        )
        return 1

    print("worker_health: ok")
    return 0


def main() -> None:
    raise SystemExit(check_worker_health())


if __name__ == "__main__":
    main()
