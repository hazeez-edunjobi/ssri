# SSRI Worker (LEGACY / DEPRECATED)

> **This package is Stage-0 scaffolding and is NOT the production SSRI worker.**
>
> The authoritative Celery worker lives in:
>
> ```text
> model/src/ssri_model/worker
> ```
>
> Entry point:
>
> ```text
> celery -A ssri_model.worker.celery_app worker -Q ssri_jobs
> ```
>
> Root Docker Compose builds and runs the `model/` image with `command: worker`.

## Why this directory remains

Historical Stage-0 Celery scaffold (no product tasks). Do not add job logic here.

## Run the real worker instead

```bash
cd model
poetry run celery -A ssri_model.worker.celery_app worker -Q ssri_jobs --loglevel=info
```

Or:

```bash
docker compose up --build worker
```
