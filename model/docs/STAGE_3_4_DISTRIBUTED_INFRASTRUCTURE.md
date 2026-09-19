# Stage 3.4 — Distributed Job Infrastructure & Production Deployment Foundation

Stage 3.4 replaces Stage 3.3 single-process operational components with production-ready, swappable distributed infrastructure while preserving all Stage 2–3.3 contracts.

## Architecture

```
Client
  │
  ▼
FastAPI (API process)
  │
  ├── Authentication (Stage 3.2)
  ├── Authorization (Stage 3.2)
  ├── Rate Limiting (in-process or Redis)
  ├── Scientific Gate (Stage 3.0)
  │
  ▼
Persistent Job Store (filesystem or PostgreSQL)
  │
  ▼
Job Executor
  ├── LocalJobExecutor (ThreadPoolExecutor — development)
  └── DistributedJobExecutor (Celery + Redis — production)
  │
  ▼
Worker Process (distributed mode)
  │
  ▼
Stage 3.0 Service Contracts
  │
  ▼
Stage 2.7 / Stage 2.8
  │
  ▼
Artifacts + Persistent Job State
```

## Component Responsibilities

| Component | Local (dev) | Distributed (prod) |
|-----------|-------------|-------------------|
| JobStore | `FileJobStore` | `DatabaseJobStore` (PostgreSQL) |
| IdempotencyStore | `FileIdempotencyStore` | `RedisIdempotencyStore` |
| RateLimiter | `RateLimiter` (in-process) | `RedisRateLimiter` |
| JobExecutor | `LocalJobExecutor` | `DistributedJobExecutor` |
| Queue | in-memory thread pool | `RedisJobQueue` + Celery |

All components are selected via `InfrastructureConfig.execution_mode` and wired through `build_infrastructure()`.

## Database Schema

Table: `ssri_jobs`

Key columns: `job_id`, `status`, `payload` (JSON), `result` (JSON), `submitted_by_key_id`, `attempt`, `max_attempts`, `worker_id`, `heartbeat_at`, `version` (optimistic locking).

Schema is initialized via SQLAlchemy `metadata.create_all()` (`init_schema()`).

## Redis Usage

| Purpose | Key pattern |
|---------|-------------|
| Idempotency | `ssri:idempotency:{principal}:{hash}` (TTL enforced) |
| Rate limiting | `ssri:ratelimit:{bucket}:{key_id}` (sorted sets) |
| Job queue | `ssri:job_queue`, `ssri:job_inflight` |
| Celery broker | configured via `SSRI_CELERY_BROKER_URL` |

## Queue Semantics

1. API creates durable job record (`queued`)
2. `DistributedJobExecutor` enqueues job ID to Redis list
3. Celery task dispatched to worker
4. Worker **claims** job (atomic `queued → running` with lease)
5. Worker executes Stage 2.7/2.8
6. Worker marks `completed` or `failed`
7. Queue entry acknowledged on terminal state

Worker crash: in-flight jobs remain in `running` until lease expires; recovery requeues when heartbeat is stale (future enhancement — lease tracking persisted in DB).

## Retry Semantics

- Configurable `max_attempts`, exponential backoff, jitter
- Retry transition: `failed → queued` (bounded)
- Never retried: auth failures, scientific gate rejection, path safety violations, invalid requests

## Idempotency

Key: `(principal_key_id, Idempotency-Key)`

- Same principal + same payload → existing job
- Same principal + different payload → 409 `IDEMPOTENCY_CONFLICT`
- Different principals → isolated
- Redis TTL enforced via `SET NX EX`

## Cancellation

Same as Stage 3.3:

- `queued` → immediate cancel
- `running` → `cancel_requested=true`; worker checks before/during execution
- Terminal states → 409 `JOB_CANNOT_CANCEL`

## Worker Recovery

- Workers claim jobs with optimistic locking (`version` column)
- Double-claim prevented at database level
- Stale worker detection via `heartbeat_at` + `job_lease_seconds`
- Celery `task_acks_late=True` — tasks re-delivered if worker dies before ack

## Health / Readiness

| Endpoint | Checks |
|----------|--------|
| `/health`, `/api/v1/health` | Liveness only (no infra deps) |
| `/api/v1/ready` | Output root + infrastructure (distributed mode) |

Distributed readiness requires PostgreSQL connectivity, schema present, and Redis ping.

## Graceful Shutdown

FastAPI lifespan hook calls `InfrastructureResources.shutdown()`:

- Stops accepting new thread-pool work (local mode)
- Disposes database engine connections
- Closes Redis connections

Workers: Celery graceful shutdown finishes current task (`task_acks_late`).

## Configuration

Environment variables (prefix `SSRI_`):

| Variable | Description |
|----------|-------------|
| `EXECUTION_MODE` | `local` (default) or `distributed` |
| `DATABASE_URL` | PostgreSQL URL (required in distributed mode) |
| `REDIS_URL` | Redis URL (required in distributed mode) |
| `CELERY_BROKER_URL` | Celery broker (defaults to Redis URL) |
| `MAX_ATTEMPTS` | Job retry limit |
| `RETRY_BACKOFF_SECONDS` | Initial retry delay |
| `JOB_LEASE_SECONDS` | Worker lease duration |
| `WORKER_HEARTBEAT_SECONDS` | Heartbeat interval |
| `WORKER_COUNT` | Local thread pool size |
| `RATE_LIMIT_ENABLED` | Enable rate limiting |

## Local Development

Default `execution_mode=local` requires no PostgreSQL or Redis:

```bash
poetry run pytest
poetry run uvicorn ssri_model.api.app:app
```

Optional infrastructure:

```bash
docker compose up -d
export SSRI_EXECUTION_MODE=distributed
export SSRI_DATABASE_URL=postgresql://ssri:ssri@localhost:5432/ssri
export SSRI_REDIS_URL=redis://localhost:6379/0
poetry run celery -A ssri_model.worker.celery_app worker -Q ssri_jobs
```

## Production Deployment

1. Deploy PostgreSQL and Redis (see `model/docker-compose.yml`)
2. Set `SSRI_EXECUTION_MODE=distributed`
3. Run API service (uvicorn)
4. Run Celery workers separately
5. Monitor `/api/v1/ready` for infrastructure health

## Security

All Stage 3.0–3.3 security properties preserved:

- Auth → Authorization → Scientific Gate → Execution order unchanged
- No credentials in API responses or logs
- Ownership checks enforced at JobService layer
- Sanitized error messages only

## Known Limitations

1. ~~Stale running job recovery requires manual requeue or future lease sweeper~~ — addressed in Stage 3.4.5 (`SSRI_LEASE_RECOVERY_ENABLED`, recovery CLI)
2. Celery worker and API must share database and Redis configuration
3. Full production validation requires running PostgreSQL + Redis + Celery (optional integration tests; see Stage 3.4.5)
4. SQLite used in unit tests; production targets PostgreSQL

## Readiness for Stage 3.5

Stage 3.4 provides durable state, distributed queue, shared rate limiting, and worker separation. Stage 3.4.5 adds lease recovery, heartbeat hardening, and operational observability. Stage 3.5 can add metrics/tracing export and horizontal autoscaling.
