# SSRI API (LEGACY / DEPRECATED)

> **This package is Stage-0 scaffolding and is NOT the production SSRI API.**
>
> The authoritative FastAPI application lives in:
>
> ```text
> model/src/ssri_model/api
> ```
>
> Entry point:
>
> ```text
> uvicorn ssri_model.api.app:app
> ```
>
> Root Docker Compose (`infra/docker-compose.yml`) builds and runs the
> `model/` image, not this package.

## Why this directory remains

Kept for historical reference and to avoid breaking old local scripts.
Do not add new product features here.

## Legacy endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Stage-0 health check only |

## Run the real API instead

```bash
cd model
poetry run uvicorn ssri_model.api.app:app --reload
```

Or via Compose from the repository root:

```bash
docker compose up --build api
```
