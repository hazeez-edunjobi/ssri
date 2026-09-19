# SSRI — SubSurface Risk Intelligence

Geospatial hazard-risk intelligence platform (subsidence, landslide, sinkhole susceptibility).

## Authoritative application

The production application is the **`model/`** Poetry package:

| Component | Module | Role |
|-----------|--------|------|
| HTTP API | `ssri_model.api.app:app` | FastAPI inference, batch, jobs, auth |
| Worker | `ssri_model.worker.celery_app` | Celery task `ssri.execute_job` |
| Recovery | `ssri_model.infrastructure.recovery` | Optional stale-lease sweeper |

**Deprecated (Stage-0 scaffolds, not production):** `api/`, `worker/`.

## Architecture

```text
Frontend (Next.js)
        │
        ▼
ssri_model.api  ──► Auth / RBAC / rate limits
        │
        ▼
   JobService ──► PostgreSQL (job state) + Redis (queue)
        │
        ▼
ssri_model.worker ──► Stage 2.7/2.8 inference ──► artifacts
```

ML pipeline (offline-capable once features exist): feature stack → dataset → U-Net → train/eval → inference → scientific validation gates → service API.

## Quick start (Docker)

```bash
cp .env.example .env
# Edit POSTGRES_PASSWORD and other secrets

docker compose -f infra/docker-compose.yml up --build -d postgres redis api worker
# optional UI:
docker compose -f infra/docker-compose.yml up --build -d frontend
```

| Service | URL |
|---------|-----|
| API docs | http://localhost:8000/docs |
| Health | http://localhost:8000/health |
| Ready | http://localhost:8000/api/v1/ready |
| Frontend | http://localhost:3000 |

Optional lease-recovery sweeper:

```bash
docker compose -f infra/docker-compose.yml --profile recovery up -d recovery
```

Verified (local Docker Desktop): API/worker images build (CPU torch), Postgres/Redis healthy, `/health` + `/api/v1/health` + `/api/v1/ready` OK, async inference job completed via Celery.
## Local development (Poetry)

```bash
cd model
poetry install
poetry run uvicorn ssri_model.api.app:app --reload
# optional worker:
poetry run celery -A ssri_model.worker.celery_app worker -Q ssri_jobs
```

Tests:

```bash
cd model
poetry run pytest
```

## Environment

See `.env.example`. Application settings use the `SSRI_*` prefix
(for example `SSRI_EXECUTION_MODE`, `SSRI_DATABASE_URL`, `SSRI_REDIS_URL`,
`SSRI_AUTH_ENABLED`).

Compose defaults to `SSRI_EXECUTION_MODE=distributed`.

## Documentation

Stage docs: `model/docs/` (Stages 2.3–3.4.5).

Scientific software correctness ≠ geological field validation. Passing tests do not claim scientific truth of hazard predictions.

## Repository layout

| Directory | Purpose |
|-----------|---------|
| `model/` | **Authoritative** ML + API + worker + infrastructure |
| `frontend/` | Next.js UI (dashboard integration in progress) |
| `infra/` | Docker Compose for the real application |
| `api/` | Deprecated Stage-0 API scaffold |
| `worker/` | Deprecated Stage-0 worker scaffold |
| `docs/` | Project docs (expanding) |
| `credentials/` | Local secrets only (gitignored `*.json`) |
