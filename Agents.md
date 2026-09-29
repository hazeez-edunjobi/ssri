# SSRI agent guide

SSRI (SubSurface Risk Intelligence) is a geospatial ground-risk platform: map a place, estimate susceptibility to **subsidence**, **landslide**, and **sinkhole**. Status: **research-ready, scientifically unvalidated, not production-qualified.** Do not describe a successful train, demo, or live assess run as geological truth or production readiness.

Product narrative lives in `About.md`. Operations live in `docs/operations.md` and `README.md`.

## Where to change code

| Path | Role |
|------|------|
| `model/` | **Authoritative** app: FastAPI, Celery worker, training, inference (`ssri_model`) |
| `frontend/` | Next.js UI: marketing, `/dashboard` assess, `/training` |
| `infra/` | Docker Compose for the real stack |
| `docs/` | Product and research docs |
| `api/`, `worker/` | **Deprecated** Stage-0 scaffolds. Do not extend them. |

API entry: `ssri_model.api.app:app`. Prefix: `/api/v1`. Worker task: `ssri.execute_job`.

## Version 4 platform

Accounts and product records use Supabase (`supabase/migrations/20260929000000_platform_v4.sql`). The browser may only see `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON_KEY`. The service-role key stays on the server.

Product routes live under `/api/v1/platform` and call the existing Stage 2.5 trainer. Do not add a second trainer, job queue, or password store. Training completion stays `NOT_VALIDATED`. `/dashboard` remains the assessment map. Account home is `/workspace`. Advanced operator training remains at `/training/operator`.

Admin access is `profiles.role = 'admin'`, set with SQL, not by matching an email in the client.

## Two model stacks — do not mix them

**Stage 2.5 (assess + manual training)**

- Model: `SSRIModel` in `model/src/ssri_model/architecture/model.py`
- Trainer: `Trainer` in `model/src/ssri_model/training/trainer.py`
- Input: `(B, 13, H, W)`. Channel order is `CHANNEL_NAMES` in `ml/constants.py`.
- Labels: `subsidence` (0), `landslide` (1), `sinkhole` (2). Nodata `-1`.
- Checkpoints: `best.pt` / `latest.pt` with `model_state_dict` and `model_config`. These are what `/api/v1/assess` and inference load.

**Foundation multitask (research only)**

- Model: `SSRIMultiTaskModel` (`architecture/multitask.py`)
- CLI: `python -m ssri_model.scripts.train_foundation_multitask`
- Heads: landslide, subsidence, **liquefaction** (not sinkhole)
- Checkpoints are **not** loadable by assess. Do not wire them into the assessment path without a new loader.

Liquefaction on marketing pages is not the live assess class. Do not rename sinkhole to liquefaction.

## Dataset layout (Stage 2.5)

```text
{dataset}/
  manifest.json
  statistics.json
  train/{id}/feature_stack.npy
  train/{id}/label.tif
  train/{id}/metadata.json
  validation/{id}/...
```

`feature_stack.npy` must be `(13, H, W)`. Train and validation splits must both be non-empty. Reuse `SSRIDataset` and `write_manifest`; do not invent a second dataset schema.

## Manual training

UI: `/training`. API: `/api/v1/training/*` (`api/routes/training.py`). Logic: `manual_training/`.

Flow: create dataset → upload Stage 2.5 zip (or register a path) → validate → `POST /training/jobs` (`JobType.TRAINING`) → poll job → registry copy of `best.pt` → optional promote.

- New runs must not overwrite an existing checkpoint. Promotion is explicit (`POST /training/models/activate`).
- Results stay `scientific_validation_status=NOT_VALIDATED`.
- Storage is under `{output_root}/training/` (`datasets/`, `runs/`, `models/`).
- Zip ingest must reject path traversal. Uploads need `python-multipart`.

Assess still takes a client `checkpoint` path. The dashboard may prefill the promoted path. Demo mode and offline `.npy` assess must keep working.

## Jobs

`JobType`: `inference`, `batch`, `training`. Local executor runs a worker callable; distributed mode enqueues Celery and `worker/tasks.py` dispatches by type. Long training must not block the HTTP handler.

## Commands

```bash
cd model
poetry install
poetry run pytest
poetry run uvicorn ssri_model.api.app:app --reload
```

Frontend: `cd frontend && npm install && npm run dev` (port 3000). Compose: `infra/docker-compose.yml`.

## Constraints

- Do not add login, roles, API keys, or auth middleware unless asked. Auth already exists and defaults off in development (`SSRI_AUTH_ENABLED`).
- Do not commit `.env`, `credentials/*.json`, catalog CSVs, full `catalog.jsonl`, or geophysics rasters over GitHub’s 100 MB limit. See `.gitignore`.
- Do not treat marketing SDK/API copy (`/v1/hazard`, `pip install ssri-python`) as implemented. Real assess route is `POST /api/v1/assess`.
- Prefer extending Stage 2.5 trainer, jobs, and assess over a parallel pipeline.
- Operator-facing errors should be plain language. Keep stack traces in logs.
