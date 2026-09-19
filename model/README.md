# SSRI Model

Authoritative SSRI ML + operational service package (`ssri-model`).

## What this package contains

| Area | Package | Status |
|------|---------|--------|
| Feature / dataset / ML | `data`, `dataset`, `ml`, `architecture` | Implemented |
| Train / eval / infer | `training`, `evaluation`, `inference`, `orchestration` | Implemented |
| Scientific gates | `scientific` | Implemented |
| Service contracts | `service` (Stage 3.0) | Implemented |
| FastAPI | `api` (Stages 3.1–3.3) | Implemented |
| Auth | `auth` (Stage 3.2) | Implemented |
| Distributed jobs | `infrastructure`, `worker` (3.4–3.4.5) | Implemented |
| Uncertainty | `uncertainty` | Placeholder (next product phase) |

## Install

```bash
cd model
poetry install
```

## Run API

```bash
poetry run uvicorn ssri_model.api.app:app --reload
```

## Run worker (distributed mode)

```bash
export SSRI_EXECUTION_MODE=distributed
export SSRI_DATABASE_URL=postgresql+psycopg://ssri:ssri@localhost:5432/ssri
export SSRI_REDIS_URL=redis://localhost:6379/0
poetry run celery -A ssri_model.worker.celery_app worker -Q ssri_jobs
```

## Docker

```bash
# from repository root
docker compose up --build api worker postgres redis
```

Image definition: `model/Dockerfile` (shared by API and worker).

## Live Earth Engine sampling

`Image.sampleRectangle` is limited to **262,144** pixels per request. Live FeatureStack acquisition tiles the SSRI UTM target grid into non-overlapping chunks (safe budget ≤250,000 px/tile), samples each tile, and mosaics them at 30 m without lowering resolution or cropping the AOI. Extremely large grids are rejected with a clear error (`EE_SAMPLE_MAX_TOTAL_PIXELS`). See `docs/production_qualification.md` §28.

## Tests

```bash
poetry run pytest
poetry run ruff check src tests
poetry run mypy src/ssri_model
```

Optional distributed integration:

```bash
docker compose -f docker-compose.yml up -d   # model/postgres+redis helper
export SSRI_INTEGRATION_TESTS=1
export SSRI_DATABASE_URL=postgresql+psycopg://ssri:ssri@localhost:5432/ssri
export SSRI_REDIS_URL=redis://localhost:6379/0
poetry run pytest tests/test_infrastructure_integration.py -v
```

## Docs

See `docs/STAGE_*.md` for stage history (2.3–3.4.5).
