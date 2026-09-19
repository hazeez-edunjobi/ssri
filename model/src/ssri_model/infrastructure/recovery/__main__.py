"""Operational CLI for stale lease recovery."""

from __future__ import annotations

import argparse
import time

from ssri_model.api.config import APIConfig
from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.factory import build_infrastructure
from ssri_model.infrastructure.recovery.service import LeaseRecoveryService


def _build_service() -> LeaseRecoveryService:
    api_config = APIConfig.from_env()
    resources = build_infrastructure(api_config)
    store = resources.job_store
    if not isinstance(store, DatabaseJobStore):
        raise RuntimeError("Lease recovery requires DatabaseJobStore")
    queue = None
    if resources.redis_client is not None:
        from ssri_model.infrastructure.redis.queue import RedisJobQueue

        queue = RedisJobQueue(resources.redis_client)
    return LeaseRecoveryService(
        store,
        api_config.infrastructure_config,
        queue=queue,
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSRI stale lease recovery sweeper")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single recovery sweep and exit",
    )
    parser.add_argument(
        "--loop",
        action="store_true",
        help="Run recovery sweeps continuously",
    )
    args = parser.parse_args(argv)
    service = _build_service()
    config = service.config
    if not config.lease_recovery_enabled:
        print("Lease recovery is disabled (SSRI_LEASE_RECOVERY_ENABLED=false).")
        return 0

    def run_once() -> None:
        result = service.recover_once()
        print(
            "recovery sweep:",
            f"scanned={result.scanned}",
            f"recovered={result.recovered}",
            f"failed={result.failed}",
            f"skipped={result.skipped}",
        )

    if args.loop:
        while True:
            run_once()
            time.sleep(config.lease_recovery_interval_seconds)
    else:
        run_once()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
