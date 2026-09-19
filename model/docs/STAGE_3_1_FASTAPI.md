# Stage 3.1 — FastAPI HTTP API

Stage 3.1 exposes the Stage 3.0 service contracts over HTTP using FastAPI.

**Operational inference success does not imply geological validation.**

## Architecture

```
Client
  │
  ▼
FastAPI (Stage 3.1)
  ├── request parsing (Pydantic)
  ├── HTTP-level validation
  └── dependency injection
  │
  ▼
Stage 3.0 Service Contracts
  ├── validate_inference_request()
  ├── validate_batch_request()
  ├── can_serve_prediction() / enforce_scientific_gate()
  └── build_provenance_record()
  │
  ▼
Stage 2.7 / Stage 2.8
  ├── run_inference()
  └── BatchRunner
  │
  ▼
GeoTIFF artifacts + metadata JSON
  │
  ▼
Typed API JSON response
```

The HTTP layer is thin. Business logic remains in existing service, inference, and orchestration modules.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Lightweight liveness |
| GET | `/api/v1/health` | Versioned liveness |
| GET | `/api/v1/ready` | Readiness (config + output root) |
| POST | `/api/v1/inference` | Single synchronous inference |
| GET | `/api/v1/inference/{request_id}` | Stored inference metadata/provenance |
| POST | `/api/v1/batch` | Batch synchronous orchestration |
| GET | `/api/v1/batch/{batch_id}/status` | Batch status |
| GET | `/api/v1/batch/{batch_id}/jobs/{job_id}` | Job status |

## Request Example — Inference

```json
POST /api/v1/inference
{
  "request_id": "req-001",
  "checkpoint": "/data/checkpoints/model.pt",
  "features": "/data/features/stack.npy",
  "manifest": "/data/manifest.json",
  "statistics": "/data/statistics.json",
  "output_format": "all",
  "scientific_validation_status": "NOT_VALIDATED",
  "scientific_validation_required": false
}
```

## Response Example — Inference

```json
{
  "request_id": "req-001",
  "status": "completed",
  "prediction_path": "...",
  "confidence_path": "...",
  "probability_path": "...",
  "metadata_path": "...",
  "scientific_validation_status": "NOT_VALIDATED",
  "provenance": {
    "request_id": "req-001",
    "combined_fingerprint": "...",
    "scientific_validation_status": "NOT_VALIDATED"
  }
}
```

## Error Model

```json
{
  "error": {
    "code": "SCIENTIFIC_GATE_REJECTED",
    "message": "Prediction serving blocked by scientific validation policy.",
    "details": {}
  }
}
```

| HTTP | Code examples |
|------|----------------|
| 400 | `INVALID_REQUEST`, `PATH_SAFETY_VIOLATION`, `INVALID_CONFIGURATION` |
| 403 | `SCIENTIFIC_GATE_REJECTED` |
| 404 | `RESOURCE_NOT_FOUND` |
| 409 | `CONFLICT` |
| 422 | `VALIDATION_ERROR` |
| 500 | `INTERNAL_ERROR` |
| 503 | `SERVICE_NOT_READY` |

Stack traces, secrets, and absolute filesystem paths are not returned to clients.

## Scientific Validation Gate

The API reuses Stage 3.0 `enforce_scientific_gate()` and never upgrades scientific status.

Preserved statuses:

- `NOT_VALIDATED`
- `DATASET_AUDITED`
- `STATISTICALLY_VALIDATED`
- `SPATIALLY_VALIDATED`
- `SCIENTIFICALLY_VALIDATED`

When `scientific_validation_required` is true (request or service config), only `SCIENTIFICALLY_VALIDATED` may proceed (HTTP 403 otherwise).

## Path Safety

All identifiers and paths pass through Stage 3.0 utilities:

- `sanitize_request_id()`
- `reject_path_traversal()`
- `ensure_output_under_root()`
- `resolve_under_output_root()`

Batch/job status endpoints resolve manifests only under the configured service `output_root`.

## Configuration

`APIConfig` wraps `ServiceConfig` and adds HTTP settings:

- `host`, `port`, `api_prefix`
- `max_batch_jobs`, `max_request_body_bytes`
- `docs_enabled`

Environment variables (optional, prefix `SSRI_API_`):

- `SSRI_API_HOST`, `SSRI_API_PORT`, `SSRI_API_OUTPUT_ROOT`
- `SSRI_API_SCIENTIFIC_VALIDATION_REQUIRED`
- `SSRI_API_ALLOW_UNVALIDATED_PREDICTIONS`

## Synchronous Execution

Stage 3.1 executes inference synchronously within the HTTP request.

There is no queue, worker pool, or background job infrastructure in this stage.

## Local Development

```bash
cd model
poetry install
poetry run uvicorn ssri_model.api.app:app --host 0.0.0.0 --port 8000
```

OpenAPI docs: `http://localhost:8000/docs`

## Testing

```bash
poetry run pytest tests/test_api_*.py -q
poetry run pytest tests/ -q
```

Tests use `TestClient` with mocked Stage 2.7/2.8 runners — no network or real ML inference.

## Limitations

- No authentication, rate limiting, or cloud deployment
- Synchronous execution only (long runs block the HTTP request)
- Filesystem path references only (no upload handling)
- Inference metadata endpoint reads stored provenance under `output_root`

## Relationship to Prior Stages

| Stage | Role |
|-------|------|
| 3.0 | Request/response contracts, validation, provenance, scientific gate |
| 2.7 | `run_inference()` execution |
| 2.8 | `BatchRunner`, status utilities |
| 2.9 | Fingerprint and scientific status semantics |

## Package Location

`model/src/ssri_model/api/`
