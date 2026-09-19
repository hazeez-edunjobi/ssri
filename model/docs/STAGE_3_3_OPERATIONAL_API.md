# Stage 3.3 — Operational API Management, Rate Limiting & Async Jobs

Stage 3.3 adds operational infrastructure around the existing SSRI inference platform without changing Stage 2.7/2.8 execution or Stage 3.0 service contracts.

## Architecture

```
Client
  ↓
FastAPI
  ↓
Authentication (Stage 3.2)
  ↓
Authorization (Stage 3.2)
  ↓
Rate Limiting (Stage 3.3, optional)
  ↓
Scientific Gate (Stage 2.9 / 3.0)
  ↓
Job Creation (async) or Direct Execution (sync)
  ↓
JobExecutor (ThreadPoolExecutor)
  ↓
Stage 3.0 validation → Stage 2.7 / Stage 2.8
  ↓
Artifacts
  ↓
Job Store (filesystem)
```

The invariant **Authentication → Authorization → Scientific Gate → Execution** is preserved for all inference and batch paths.

## API Key Management

Administrative endpoints under `/api/v1/auth/keys` require `Permission.MANAGE_AUTH` (admin role).

| Method | Path | Description |
|--------|------|-------------|
| POST | `/api/v1/auth/keys` | Create key (plaintext returned once) |
| GET | `/api/v1/auth/keys` | List keys (no secrets) |
| GET | `/api/v1/auth/keys/{key_id}` | Get key metadata |
| POST | `/api/v1/auth/keys/{key_id}/disable` | Disable key immediately |
| POST | `/api/v1/auth/keys/{key_id}/enable` | Re-enable key |
| DELETE | `/api/v1/auth/keys/{key_id}` | Delete key (soft audit via events) |

Secrets are stored only as PBKDF2-HMAC-SHA256 hashes. Plaintext keys are never persisted, logged, or returned after creation.

Audit events: `key_created`, `key_disabled`, `key_enabled`, `key_deleted`, plus existing `authentication_success` / `authentication_failure`.

## Rate Limiting

In-process, thread-safe sliding-window limiter keyed by API key identity. Applied **after** authentication on protected endpoints.

| Bucket | Default (when enabled) | Endpoints |
|--------|------------------------|-----------|
| inference | 60 req / 60s | `POST /inference/async` |
| batch | 30 req / 60s | `POST /batch/async` |
| status | 120 req / 60s | Job/batch status reads |

Health endpoints (`/health`, `/api/v1/health`, `/api/v1/ready`) are not rate-limited.

Exceeded limits return HTTP 429 with `RATE_LIMIT_EXCEEDED`, `Retry-After` header, and `retry_after_seconds` in the error body.

Rate limiting is **disabled by default** (`rate_limit_enabled=false`) for backward compatibility.

## Async Job Lifecycle

### Submission

| Method | Path | Permission | Response |
|--------|------|------------|----------|
| POST | `/api/v1/inference/async` | RUN_INFERENCE | 202 + job_id |
| POST | `/api/v1/batch/async` | RUN_BATCH | 202 + job_id |

Flow: authenticate → authorize → rate limit → validate → scientific gate → create job → persist → submit to executor → return immediately.

### Status & Cancellation

| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/v1/jobs/{job_id}` | READ_STATUS |
| POST | `/api/v1/jobs/{job_id}/cancel` | RUN_INFERENCE (owner or admin) |

### Job States

| Status | Meaning |
|--------|---------|
| `queued` | Accepted, waiting for worker |
| `running` | Worker executing |
| `completed` | Finished successfully |
| `failed` | Execution error (sanitized message) |
| `cancelled` | Cancelled while queued or cancel requested while running |

**Execution status** is separate from **scientific_validation_status** (`NOT_VALIDATED` … `SCIENTIFICALLY_VALIDATED`). Async execution never auto-upgrades scientific status.

### Storage Layout

```
{output_root}/jobs/
  {job_id}/
    job.json      # durable metadata (atomic writes)
    result.json   # completion payload
```

Idempotency mappings: `{output_root}/jobs/idempotency/{principal_key_id}/{hash}.json`

## Cancellation Semantics

- **Queued** jobs: cancelled immediately (`status=cancelled`).
- **Running** jobs: `cancel_requested=true`; worker checks flag before/during execution. ThreadPoolExecutor cannot forcibly stop in-flight Python work — a running job may complete even after cancel is requested.
- **Completed / failed / cancelled** jobs cannot be cancelled (409 `JOB_CANNOT_CANCEL`).

## Idempotency

Header: `Idempotency-Key` (safe identifier, max 128 chars).

Same authenticated principal + same key + same request fingerprint → returns existing job (no duplicate work).

Different principals with the same key do **not** collide.

Different payload with same key → 409 `IDEMPOTENCY_CONFLICT`.

## Ownership & Access Control

Jobs record `submitted_by_key_id`. Access rules:

- Creator can read/cancel own jobs
- Admin can read all jobs
- Other principals receive 404 (no enumeration leak)

## Configuration

`OperationalConfig` on `APIConfig.operational_config`:

| Setting | Default | Description |
|---------|---------|-------------|
| `async_enabled` | `true` | Enable async endpoints |
| `worker_count` | `2` | Thread pool size |
| `max_queue_size` | `100` | Max queued+running jobs |
| `job_store_root` | `"jobs"` | Relative to output_root |
| `rate_limit_enabled` | `false` | Enable rate limiting |
| `inference_requests_per_window` | `60` | Inference limit |
| `inference_window_seconds` | `60.0` | Inference window |
| `batch_requests_per_window` | `30` | Batch limit |
| `batch_window_seconds` | `60.0` | Batch window |
| `status_requests_per_window` | `120` | Status limit |
| `status_window_seconds` | `60.0` | Status window |
| `idempotency_ttl_seconds` | `86400` | Idempotency TTL (reserved) |

## Security Controls

- Path traversal / null-byte rejection on job IDs and paths
- No stack traces or filesystem internals in API errors
- No secrets in logs or responses after key creation
- Scientific gate cannot be bypassed via async paths
- Rate limiting never bypasses authorization

## Operational Limitations

1. **ThreadPoolExecutor is not durable compute** — in-flight work is lost on process termination; job metadata persists but may show `running` or `queued`.
2. **Filesystem job store is single-host oriented** — not suitable for multi-instance deployments without shared storage.
3. **In-process rate limiting** — not shared across processes; Redis/external limiter is future work (Stage 3.4+).
4. **Async execution does not imply scientific validation** — status reflects execution only.

## Backward Compatibility

Existing synchronous endpoints remain unchanged:

- `POST /api/v1/inference`
- `POST /api/v1/batch`
- All Stage 3.1/3.2 health, metadata, and batch status routes

Default configuration preserves prior behavior (auth optional in dev, rate limiting off).

## Readiness for Stage 3.4

Stage 3.3 isolates replaceable abstractions:

- `JobExecutor` — swap ThreadPoolExecutor for Celery/Redis/cloud queue
- `JobStore` / `IdempotencyStore` — swap filesystem for database
- `RateLimiter` — swap in-process for distributed limiter

Service contracts and Stage 2.7/2.8 runners remain untouched.
