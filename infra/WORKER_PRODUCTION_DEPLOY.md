# SSRI Celery worker — production deploy preparation

Authoritative image: `model/Dockerfile` (shared with the API).  
Entrypoint roles: `model/docker-entrypoint.sh`.

## Exact start command

Docker / Render “Docker Command” (preferred):

```text
worker
```

Equivalent expanded command:

```sh
python -m celery -A ssri_model.worker.celery_app worker \
  --loglevel="${LOG_LEVEL:-info}" \
  -Q ssri_jobs \
  --concurrency="${SSRI_CELERY_CONCURRENCY:-1}"
```

Registered task name: `ssri.execute_job`  
Celery queue: `ssri_jobs`

Health probe (Compose / optional):

```sh
python -m ssri_model.worker.health
```

## Hosting decision

- Run as a **separate always-on process**, not inside the FastAPI web service.
- Prefer a Render **Background Worker** (or equivalent) using the same Docker image as `ssri-api`.
- Do **not** rely on a free web service that sleeps; Celery must stay connected to the broker.
- Paid always-on compute requires owner approval if the account is not already entitled.

Local / staging reference: `infra/docker-compose.yml` service `worker` (`command: ["worker"]`).

## Environment variables (names only — copy values from the API service)

Required for distributed mode:

| Name | Notes |
|------|--------|
| `SSRI_EXECUTION_MODE` | `distributed` |
| `SSRI_DATABASE_URL` | Same Postgres as the API |
| `SSRI_REDIS_URL` | Same Upstash URL; use `rediss://` for TLS |
| `SSRI_CELERY_BROKER_URL` | Optional; defaults to `SSRI_REDIS_URL` |
| `SSRI_CELERY_RESULT_BACKEND` | Optional; defaults to broker |
| `SSRI_CELERY_CONCURRENCY` | Prefer `1` unless sized otherwise |
| `SSRI_API_OUTPUT_ROOT` | Must match API artifact root / volume |
| Object storage vars | Same as API if used for GeoTIFF / artifacts |

Also copy any auth, Supabase, GEE, OpenTopo, and geophysics paths the jobs you expect actually need.

Do **not** set `SSRI_EXECUTION_MODE=local` on the worker.

## Render Background Worker checklist

1. New service → **Background Worker**.
2. Connect the same GitHub repo / Dockerfile root as the API (`model/` context, `Dockerfile`).
3. Docker Command: `worker`.
4. Paste env from the API (especially Redis `rediss://` and Postgres).
5. Attach the same persistent disk / object storage assumptions as the API for checkpoints and outputs.
6. Deploy and open logs.
7. Expect Celery to connect to the broker and listen on queue `ssri_jobs`.
8. Confirm `python -m ssri_model.worker.health` would pass (broker ping + celery import).

## Post-deploy verification (owner or agent with credentials)

1. `GET https://ssri-api.onrender.com/api/v1/ready` remains ready.
2. Authenticated `POST /api/v1/inference/async` (or a training job).
3. Job row created; Celery delivers `ssri.execute_job`.
4. Worker logs show claim/execute/complete (or retryable failure with a clear error).
5. `GET /api/v1/jobs/{job_id}` returns the terminal status and result paths/URLs.

Until step 2–5 succeed, do not claim the async pipeline is production-ready.
