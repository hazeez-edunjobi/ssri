# Stage 3.4.5 — Distributed Infrastructure Hardening

Stage 3.4.5 hardens the distributed execution layer introduced in Stage 3.4. It does **not** change ML inference, training, scientific validation, or Stage 3.0 service contracts. Default local mode remains backward-compatible.

## Objectives

1. Automated stale-worker lease recovery
2. Worker heartbeat handling with optimistic locking
3. Retry/requeue safety
4. Queue/database consistency
5. Graceful worker shutdown
6. Infrastructure readiness correctness
7. Optional distributed integration tests
8. Operational observability hooks

## Stale Lease Recovery

Running jobs periodically update `heartbeat_at`. When a worker stops heartbeating beyond `SSRI_JOB_LEASE_SECONDS`, a recovery sweeper can safely requeue or fail the job.

**Behavior:**

- Jobs in `running` with stale `heartbeat_at` are candidates.
- If `attempt < max_attempts`: transition to `queued`, increment recovery metadata, re-enqueue.
- If `attempt >= max_attempts`: transition to `failed` with `LEASE_EXPIRED`.
- Recovery uses optimistic locking; concurrent sweeps are idempotent.
- Terminal jobs are never recovered.
- Fresh heartbeats are never overwritten.

**CLI:**

```bash
export SSRI_EXECUTION_MODE=distributed
export SSRI_DATABASE_URL=postgresql://ssri:ssri@localhost:5432/ssri
export SSRI_REDIS_URL=redis://localhost:6379/0
export SSRI_LEASE_RECOVERY_ENABLED=true

# One-shot (cron / Kubernetes Job)
poetry run python -m ssri_model.infrastructure.recovery --once

# Continuous sweeper
poetry run python -m ssri_model.infrastructure.recovery --loop
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `SSRI_LEASE_RECOVERY_ENABLED` | `false` | Enable recovery sweeper |
| `SSRI_LEASE_RECOVERY_INTERVAL_SECONDS` | `60` | Loop interval for `--loop` |
| `SSRI_LEASE_RECOVERY_BATCH_SIZE` | `50` | Max jobs per sweep |
| `SSRI_JOB_LEASE_SECONDS` | `300` | Stale lease threshold |
| `SSRI_WORKER_HEARTBEAT_SECONDS` | `30` | Heartbeat interval (must be < lease) |

Invalid combinations (e.g. heartbeat ≥ lease, `max_attempts < 1`) fail fast at startup.

## Worker Heartbeat

`HeartbeatController` refreshes `heartbeat_at` during job execution using version + expected-heartbeat checks. Stale workers cannot overwrite a newer heartbeat. Heartbeats stop on terminal state, ownership change, shutdown, or failed optimistic update.

## Retry Safety

`is_retryable_failure()` distinguishes transient infrastructure errors from non-retryable failures:

- **Never retried:** auth, authorization, scientific gate, path safety, invalid config/request, idempotency conflicts
- **May retry:** transient infrastructure/runtime failures within `max_attempts`

Retries persist state atomically via database transitions and bounded exponential backoff with jitter.

## Queue / Database Consistency

The database is the source of truth. Redis is delivery-only.

- `claim()` prevents double execution.
- Duplicate Celery delivery is harmless (claim returns `None`).
- Unknown jobs: acknowledge and log `job_claim_skipped`.
- Terminal jobs: skip execution and acknowledge.
- Worker crash: stale lease recovery requeues when attempts remain.

## Graceful Worker Shutdown

Celery `worker_shutting_down` sets a process-wide shutdown flag:

- New tasks are skipped (`worker_shutdown` event).
- In-flight jobs finish current work where practical.
- Heartbeat threads stop cleanly in `finally`.
- Unfinished jobs rely on lease recovery / retry semantics; they are not marked completed.

## Readiness

`GET /api/v1/ready` in distributed mode verifies:

- Configuration consistency
- PostgreSQL reachable and schema present
- Redis reachable
- Queue reachable

Local mode retains lightweight readiness (no external dependencies). Readiness does not run ML inference and does not expose credentials.

## Observability

Structured operational events via `log_operational_event()`:

`job_submitted`, `job_claimed`, `job_completed`, `job_failed`, `job_requeued`, `job_recovered`, `heartbeat_failed`, `infrastructure_unavailable`, `worker_shutdown`

Sensitive fields (credentials, URLs, payloads) are filtered from logs.

## Integration Tests

Optional tests require real PostgreSQL and Redis:

```bash
docker compose -f model/docker-compose.yml up -d
export SSRI_INTEGRATION_TESTS=1
export SSRI_DATABASE_URL=postgresql://ssri:ssri@localhost:5432/ssri
export SSRI_REDIS_URL=redis://localhost:6379/0
poetry run pytest tests/test_infrastructure_integration.py -v
```

Baseline unit tests continue to use SQLite and fakeredis; external services are not required.

## Database Indexes

PostgreSQL/SQLite schema includes indexes on `job_id`, `status`, `heartbeat_at`, `submitted_by_key_id`, and `created_at` to support recovery sweeps and operational queries.

## Security

All Stage 3.0–3.4 security properties are preserved. Infrastructure hardening does not imply scientific validity.

## Known Limitations

1. Recovery sweeper must be deployed separately (CLI or cron); it is disabled by default.
2. Full end-to-end Celery integration tests are optional and environment-gated.
3. SQLite is used in unit tests; production targets PostgreSQL.

## Readiness for Stage 3.5

Stage 3.4.5 provides production-safe lease recovery, heartbeat enforcement, retry classification, and operational hooks. Stage 3.5 can add metrics/tracing export and horizontal autoscaling policies.
