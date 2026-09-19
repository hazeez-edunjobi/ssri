"""Verify stale lease recovery against a live Postgres job store.

Usage (from host with DB URL, or inside api/recovery container):

  poetry run python scripts/verify_lease_recovery.py

Requires SSRI_DATABASE_URL. Does not require Celery — exercises the durable
DB recovery path (requeue or fail) used by LeaseRecoveryService.
"""

from __future__ import annotations

import os
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Allow running as scripts/verify_lease_recovery.py without install quirks.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from ssri_model.infrastructure.database.job_store import DatabaseJobStore
from ssri_model.infrastructure.database.schema import create_database_engine, init_schema
from ssri_model.jobs.models import JobRecord, JobStatus, JobType
from ssri_model.jobs.service import utc_now_iso


def main() -> int:
    database_url = os.getenv("SSRI_DATABASE_URL")
    if not database_url:
        print("SSRI_DATABASE_URL is required", file=sys.stderr)
        return 2

    lease_seconds = int(os.getenv("SSRI_JOB_LEASE_SECONDS", "300"))
    engine = create_database_engine(database_url)
    init_schema(engine)
    store = DatabaseJobStore(engine, auto_init=False)

    now = datetime.now(timezone.utc)
    stale_heartbeat = (now - timedelta(seconds=lease_seconds + 60)).isoformat()
    job_id = store.generate_job_id()
    record = JobRecord(
        job_id=job_id,
        request_id="verify-lease-recovery",
        job_type=JobType.INFERENCE,
        status=JobStatus.RUNNING,
        submitted_by_key_id="abc1234567890abcd",
        auth_role="operator",
        scientific_validation_status="NOT_VALIDATED",
        payload={"request_id": "verify-lease-recovery"},
        created_at=utc_now_iso(),
        queued_at=utc_now_iso(),
        started_at=utc_now_iso(),
        worker_id="dead-worker",
        attempt=1,
        max_attempts=3,
        heartbeat_at=stale_heartbeat,
        version=1,
    )
    store.save(record)
    print(f"seeded_stale_job={job_id} heartbeat_at={stale_heartbeat}")

    cutoff = now.isoformat()
    updated = store.recover_stale_job(
        job_id,
        heartbeat_cutoff=cutoff,
        recovered_at=utc_now_iso(),
    )
    print(
        f"status={updated.status.value if updated else None} "
        f"error_code={updated.error_code if updated else None} "
        f"recovery_count={updated.recovery_count if updated else None}"
    )
    store.close()
    if updated is None or updated.status != JobStatus.QUEUED:
        print("FAIL: expected requeue to QUEUED", file=sys.stderr)
        return 1
    print("PASS: stale lease recovery requeued the job")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
