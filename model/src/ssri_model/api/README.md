# SSRI FastAPI HTTP API (Stage 3.1)

Thin HTTP boundary over Stage 3.0 service contracts.

## Endpoints

- `GET /health`
- `GET /api/v1/health`
- `GET /api/v1/ready`
- `POST /api/v1/inference`
- `GET /api/v1/inference/{request_id}`
- `POST /api/v1/batch`
- `GET /api/v1/batch/{batch_id}/status`
- `GET /api/v1/batch/{batch_id}/jobs/{job_id}`

## Local development

```bash
poetry run uvicorn ssri_model.api.app:app --host 0.0.0.0 --port 8000
```

## Documentation

See `model/docs/STAGE_3_1_FASTAPI.md`.

**Operational inference success does not imply geological validation.**
