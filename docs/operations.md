# SSRI Platform Operations

## Production path

```text
docker compose -f infra/docker-compose.yml up --build -d
  → postgres + redis
  → ssri_model.api (model/Dockerfile command=api)
  → ssri_model.worker (command=worker)
  → frontend (optional)
```

Recovery sweeper (optional profile):

```bash
docker compose -f infra/docker-compose.yml --profile recovery up -d recovery
```

### Docker image notes

* Images use **CPU torch** (`torch==2.5.1+cpu`). The Poetry lock may resolve a newer CUDA torch on Linux; the Dockerfile filters CUDA/nvidia/triton packages via `model/docker/filter_cpu_requirements.py`.
* Runtime needs shared libs for rasterio (`libexpat1`, etc.).

### Verified runtime checks

On a working Docker Desktop host:

1. `docker compose -f infra/docker-compose.yml config --quiet`
2. `docker compose -f infra/docker-compose.yml build api worker`
3. `docker compose -f infra/docker-compose.yml up -d postgres redis api worker`
4. `GET /health`, `GET /api/v1/health`, `GET /api/v1/ready` → ready with postgres/redis/queue ok
5. Async job: `POST /api/v1/inference/async` → worker `ssri.execute_job` → `GET /api/v1/jobs/{id}` completed

Helper: `model/scripts/docker_e2e_prepare_job.py` (run inside the API container).

## Health vs readiness

| Endpoint | Meaning |
|----------|---------|
| `GET /health` | Process alive |
| `GET /api/v1/health` | API liveness |
| `GET /api/v1/ready` | Config + output root + infrastructure (Postgres/Redis in distributed mode) |

## Assessment API

`POST /api/v1/assess`

Supported:

* Offline `features` (.npy) + `checkpoint` → uncertainty-aware hazard profiles
* Optional `produce_geotiff=true` → local/S3 object storage + signed URL
* Live `point` / `polygon_geojson` when `SSRI_LIVE_ACQUISITION_ENABLED=true` and GEE/OpenTopo are configured

Live acquisition without credentials returns an explicit configuration error (not silent success).

## Object storage

| Env | Purpose |
|-----|---------|
| `SSRI_OBJECT_STORAGE_BACKEND` | `local` (default) / `s3` / `minio` / `r2` |
| `SSRI_OBJECT_STORAGE_ROOT` | Local filesystem root |
| `SSRI_OBJECT_STORAGE_BUCKET` | S3-compatible bucket |
| `SSRI_OBJECT_STORAGE_ENDPOINT` | Optional custom endpoint |
| `SSRI_OBJECT_STORAGE_URL_EXPIRES` | Signed URL TTL seconds |

## Performance measurement

```bash
cd model
poetry run python scripts/measure_performance.py --base-url http://127.0.0.1:8000 --samples 20
```

Do not invent latency targets — report measured p50/p95/p99 only.

## Security defaults

* Development: auth may be disabled (`SSRI_AUTH_ENABLED=false`)
* Production: auth cannot be disabled; rate limits default on; client scientific status is not trusted
* Never bake `credentials/*.json`, Earth Engine keys, or `.env` into images

## Scientific integrity

Passing software tests ≠ geological validity of hazard predictions.

See also:

* `docs/model_card.md`
* `docs/uncertainty.md`
* `docs/security_audit.md`
