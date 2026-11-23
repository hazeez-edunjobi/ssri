# SSRI Administrator & Technical Guide

## Architecture

| Component | Location / role |
|---|---|
| Frontend | `frontend/` — Next.js (App Router) |
| API | `model/src/ssri_model/api/` — FastAPI, prefix `/api/v1` |
| Worker | Celery `ssri.execute_job` via `ssri_model.worker` |
| Geological catalogue | `ssri_model.geological.*` under `{output_root}/geological/` |
| Stage 2.5 ML | `SSRIModel` 13-channel assess/train |
| Postgres | Platform accounts / product records (Supabase-compatible) |
| Redis | Celery broker/backend |
| Outputs | `data/outputs/` (local) or configured `SSRI_OUTPUT_ROOT` |

## Environment variables (names only — never commit secrets)

Typical local / host names:

- `SSRI_OUTPUT_ROOT`, `SSRI_AUTH_ENABLED`, `SSRI_AUTH_DEVELOPMENT_MODE` (must be false in production)
- `SSRI_ENVIRONMENT` / `ENVIRONMENT` (`production` disables demo mode and wildcard CORS)
- `SSRI_CORS_ORIGINS` — explicit frontend origins only (no `*`)
- `SSRI_DEMO_MODE` — forced off in production/staging
- `DATABASE_URL` / Supabase URL + keys (`NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON_KEY`; service role server-only)
- `CELERY_BROKER_URL`, `CELERY_RESULT_BACKEND` (or `SSRI_*` equivalents)
- `NEXT_PUBLIC_API_URL`, optional `NEXT_PUBLIC_MAP_STYLE_URL`, `NEXT_PUBLIC_SSRI_API_KEY` (operator machines only)

Production must keep `SSRI_AUTH_ENABLED=true` (or platform equivalent) and must not ship development bypasses. The production gate (`ssri_model.api.production_gate`) refuses go-live when auth is off, development mode is on, or JWT/key store is missing.

## Local startup (reference)

```powershell
# API
cd model
poetry run uvicorn ssri_model.api.app:app --host 127.0.0.1 --port 8000

# Worker
poetry run celery -A ssri_model.worker.celery_app worker --loglevel=info -Q ssri_jobs --concurrency=1 --pool=solo

# Frontend
cd frontend
npm run dev
```

Compose stack: `infra/docker-compose.yml` (Postgres and related services).

## Health

- `GET /api/v1/health`
- `GET /api/v1/ready` (registry / readiness)

## User management

Admin role is `profiles.role = 'admin'` via SQL — not by matching email in the client. Geological mutations require `manage_geological`.

## Backup & recovery

Back up:

1. PostgreSQL / Supabase database.
2. `{output_root}` including `geological/datasets/*/original/` and `working/derived/`.
3. Model registry checkpoints under the configured models root.

Restore DB first, then filesystem outputs, then restart API + worker.

## Troubleshooting

| Symptom | Check |
|---|---|
| World-scale empty map | Basemap style; viewport should still fit SW Nigeria defaults |
| Geological map footprint missing | `display_bbox_wgs84` only after verified CRS transform |
| Celery jobs stuck | Redis URL, worker queue `ssri_jobs`, shared output root |
| Auth failures | `SSRI_AUTH_ENABLED`, Supabase session, operator API key |
| TMI “blocked” | Validation FAIL or `can_process=false` — read check messages |

Never paste production secrets into tickets or documentation.
