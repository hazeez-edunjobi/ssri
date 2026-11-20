# SSRI — Production infrastructure readiness investigation

**Probe UTC:** 2026-11-20T07:11:04Z  
**API:** `https://ssri-api.onrender.com`  
**Frontend:** `https://ssri-gamma.vercel.app`  
**Git baseline at investigation start:** `0654930` on `main` / `origin/main`  
**Investigation commit (local, not pushed — no prod redeploy):** `4a7528c`

---

## Final verdict

**INFRASTRUCTURE NOT READY**

The API process is **alive** (`/health` 200). Distributed readiness is **failed** because Redis **PING does not succeed**, so the job queue never initializes. Exact Redis exception class could not be read from Render logs (dashboard login wall; no API token). Production was **not** redeployed as part of this investigation.

---

## Confirmed production evidence (re-probed)

| Endpoint | Status | Observation |
|----------|--------|-------------|
| `GET /` | 404 | Expected (no root route) |
| `GET /openapi.json` | 200 | Contract live |
| `GET /health` | 200 | `ssri-inference` ok |
| `GET /api/v1/health` | 200 | Process liveness ok |
| `GET /api/v1/ready` | **503** | `SERVICE_NOT_READY` |

Readiness components:

- `configuration`: ok  
- `postgresql`: ok / connected  
- `redis`: unavailable / **`ping_failed`**  
- `queue`: unavailable / **`unconfigured`**  
- `mode`: **distributed**

This is **not** an API outage.

---

## Redis failure cause

### What `ping_failed` means in code

Files:

- `model/src/ssri_model/infrastructure/health.py` — `check_infrastructure_health`
- `model/src/ssri_model/infrastructure/redis/client.py` — `create_redis_client`, `ping_redis` / `ping_redis_with_reason`
- `model/src/ssri_model/infrastructure/config.py` — `InfrastructureConfig.from_env`

Logic:

1. Distributed mode requires `SSRI_REDIS_URL` (`InfrastructureConfig.from_env(prefix="SSRI_")`).
2. If `redis_url` were missing, readiness detail would be `unconfigured`.
3. Production reports **`ping_failed`** ⇒ **`SSRI_REDIS_URL` is set**, client construction did not raise into the outer `except`, and **PING did not succeed**.
4. Prior to this investigation, `ping_redis()` **swallowed all exceptions** and returned `False`, so readiness JSON could not expose `TimeoutError` / `AuthenticationError` / `ConnectionError`. Render logs were not accessible to recover the underlying exception.

### Likely operational causes (ranked)

Without Render env/log access, exact cause is not proven. Given `ping_failed` (URL present):

1. Redis instance stopped, deleted, or unreachable from the API private network.  
2. Wrong host/port in `SSRI_REDIS_URL`.  
3. Auth mismatch (password/ACL).  
4. TLS mismatch (`redis://` vs required `rediss://`, or missing TLS).  
5. Network policy / firewall between API service and Redis.

Supported schemes in code: `redis://`, `rediss://`, `unix://`.

### Env var names (values never printed)

| Name | Role |
|------|------|
| `SSRI_EXECUTION_MODE` | Must be `distributed` in prod (confirmed by ready payload) |
| `SSRI_REDIS_URL` | Required Redis URL for readiness + queue |
| `SSRI_CELERY_BROKER_URL` | Defaults to Redis URL if unset |
| `SSRI_CELERY_RESULT_BACKEND` | Defaults to Redis URL if unset |
| `SSRI_DATABASE_URL` | Postgres (connected in prod) |
| `REDIS_URL` | Compose/docs alias — **not** read by `InfrastructureConfig.from_env` (only `SSRI_REDIS_URL`) |

---

## Queue configuration failure cause

Queue readiness is **secondary** to Redis.

In `check_infrastructure_health`:

- Queue probe (`RedisJobQueue.depth()` on key `ssri:job_queue`) runs **only after** Redis PING succeeds.
- While Redis fails, queue detail remains **`unconfigured`**.

So queue is not independently misconfigured in the readiness sense; it never gets a chance to initialize. Celery broker/result URLs should still match the same Redis for the worker once Redis is healthy.

Queue implementation: `model/src/ssri_model/infrastructure/redis/queue.py` (`RedisJobQueue`).

---

## Readiness → HTTP 503

`model/src/ssri_model/api/routes/health.py` → `readiness()`:

- Validates service config, probes output root writability.
- Calls `check_infrastructure_health`.
- If `infra.ready` is false → **503** `SERVICE_NOT_READY` with component details.
- Distributed ready requires: configuration **and** postgres **and** redis **and** queue.

Local mode short-circuits ready=true (not used in production; do **not** switch).

---

## Render API / worker deployment status

| Component | Status |
|-----------|--------|
| API (`ssri-api.onrender.com`) | **Deployed / reachable** (health 200) |
| PostgreSQL dependency | **Connected** (from ready payload) |
| Redis dependency | **Unreachable to PING** |
| Worker process | **NOT VERIFIED** — no public worker health URL; Render dashboard requires login; docs mention Compose worker / possible Railway historically |
| Render env inspection | **Blocked** — `https://dashboard.render.com/login-next` (hCaptcha); no `RENDER_API_KEY` in environment |

No Redis/worker redeploy was performed.

---

## Dashboard health indicator defect

**Confirmed defect.**

`frontend/app/dashboard/page.tsx` previously:

1. Called `getHealth()` then `getReady()`.
2. Any failure → `apiStatus = "down"`.
3. UI label for `"down"` was **“unreachable”**.

Because `getReady()` fails on 503, a live API with failed Redis was labelled **unreachable**.

### Corrective code (this investigation; not yet production-deployed)

- Status model: `ok` | `degraded` | `down`.
- Health OK + ready fail → **“reachable · infrastructure not ready”**.
- Helper: `frontend/lib/apiHealthStatus.ts` (+ unit tests).
- Redis readiness detail now preserves exception **type** only via `ping_redis_with_reason` (no secrets). Bounded socket timeouts (5s) on Redis client construction.

These fixes improve honesty and next-diagnosis; they **do not** make Redis ready.

---

## Minimal corrective action (operations)

1. Sign in to Render (or supply a scoped API token).  
2. Confirm a live Redis/Key Value instance on the same network as the API (and worker).  
3. Set matching env on **API and worker**:
   - `SSRI_EXECUTION_MODE=distributed`
   - `SSRI_REDIS_URL` (use `rediss://` if TLS is required)
   - `SSRI_CELERY_BROKER_URL` / `SSRI_CELERY_RESULT_BACKEND` (same broker unless intentionally split)
4. Redeploy API + worker.  
5. Re-check `GET /api/v1/ready` → redis `connected`, queue `reachable`, HTTP 200.  
6. Confirm worker consumes a harmless test job.  
7. Deploy the dashboard health-label fix so the UI no longer says “unreachable” on readiness-only failure.

Do **not** set execution mode to `local` to hide the failure. Do **not** weaken `/ready`.

---

## Tests and verification results

| Check | Result |
|-------|--------|
| Production `/health` | **PASS** (200) |
| Production `/ready` | **FAIL** (503 redis `ping_failed`) |
| Render env/logs | **UNABLE TO VERIFY** (auth wall) |
| Worker running / same Redis | **UNABLE TO VERIFY** |
| Unit: `ping_redis_with_reason` exception type only | Added (run with model pytest) |
| Unit: dashboard health label mapping | Added (`apiHealthStatus.test.ts`) |
| Frontend typecheck / unit suite | Run as part of this pass |
| Redis independently verified healthy in prod | **No** |

---

## Remaining operational blockers

1. Redis PING failure in production (primary).  
2. Queue uninitialized until Redis is healthy.  
3. Worker presence/config unverified.  
4. No Render operator session/token in this environment.  
5. Dashboard mislabel still live on Vercel until the FE fix is deployed.  
6. After Redis is fixed, deploy diagnostic readiness detail so any future failure shows `ping_failed:<ExceptionType>`.

---

## Exact files involved

| Area | Path |
|------|------|
| Readiness route | `model/src/ssri_model/api/routes/health.py` |
| Infra health | `model/src/ssri_model/infrastructure/health.py` |
| Redis client | `model/src/ssri_model/infrastructure/redis/client.py` |
| Job queue | `model/src/ssri_model/infrastructure/redis/queue.py` |
| Env config | `model/src/ssri_model/infrastructure/config.py` |
| API wiring | `model/src/ssri_model/api/config.py` (`InfrastructureConfig.from_env`) |
| Dashboard indicator | `frontend/app/dashboard/page.tsx` |
| Indicator helper | `frontend/lib/apiHealthStatus.ts` |
