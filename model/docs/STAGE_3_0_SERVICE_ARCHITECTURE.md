# Stage 3.0 — Operational Deployment Architecture

Stage 3.0 defines typed service contracts for exposing the existing SSRI
inference pipeline as a production-oriented service in later Stage 3.x work.

**Stage 3.0 defines service contracts only. It does not expose an HTTP API and
does not claim scientific validation of hazard predictions.**

## Architecture

```
Client
  │
  ▼
Future HTTP API (Stage 3.1+)
  │
  ▼
Service Contract Layer (Stage 3.0)
  │
  ├── InferenceRequest ──► Stage 2.7 run_inference / InferenceConfig
  └── BatchInferenceRequest ──► Stage 2.8 BatchRunner / BatchConfig
          │
          ▼
   Prediction Artifacts (GeoTIFF + inference.json)
          │
          ▼
   ProvenanceRecord + scientific_validation_status
```

The service package **adapts** existing Stage 2.7–2.9 APIs. It does not replace
or modify inference, orchestration, or scientific validation internals.

## Service Boundaries

| Layer | Responsibility |
|-------|----------------|
| `ServiceConfig` | Operational limits, defaults, scientific policy flags |
| `requests.py` | Typed input contracts |
| `responses.py` | Typed output contracts |
| `validation.py` | Early boundary checks + path safety |
| `provenance.py` | Fingerprint-backed lineage metadata |
| Stage 2.7 | Actual single inference execution |
| Stage 2.8 | Actual batch orchestration |
| Stage 2.9 | Scientific validation semantics |

## Request / Response Contracts

### InferenceRequest

- `request_id`, `checkpoint`, `features`, `manifest`, `statistics`
- `output_format` (`geotiff`, `all`)
- optional `tile_size`, `overlap`, `batch_size`
- `scientific_validation_required`
- adapter: `to_inference_config()` → Stage 2.7

### BatchInferenceRequest

- `request_id`, `jobs_file`, `output_root`, `resume`
- adapter: `to_batch_config()` → Stage 2.8

### InferenceResponse / BatchInferenceResponse

Execution statuses are separate from scientific validation status.

Inference execution: `pending`, `running`, `completed`, `failed`

Batch execution adds: `completed_with_errors`

## Provenance

`ProvenanceRecord` reuses Stage 2.9 `compute_reproducibility_fingerprints()`:

- `dataset_fingerprint`
- `statistics_fingerprint`
- `checkpoint_fingerprint`
- `configuration_fingerprint`
- `combined_fingerprint`

No second fingerprint system is introduced.

## Security Boundary

Service-level utilities reject:

- path traversal (`..`)
- null bytes in identifiers
- unsafe request IDs
- outputs outside configured `output_root`

No shell execution. No secrets in configuration.

## Scientific Validation Semantics

Operational inference success ≠ geological validation.

`can_serve_prediction()` policy:

1. `scientific_validation_required=True` → only `SCIENTIFICALLY_VALIDATED`
2. `scientific_validation_required=False` and `allow_unvalidated_predictions=False`
   → block `NOT_VALIDATED`
3. Otherwise allow according to configuration

Statuses are never upgraded automatically:

- `NOT_VALIDATED`
- `DATASET_AUDITED`
- `STATISTICALLY_VALIDATED`
- `SPATIALLY_VALIDATED`
- `SCIENTIFICALLY_VALIDATED`

## Output Format Contract

| Format | Artifacts |
|--------|-----------|
| `geotiff` / `all` | `prediction.tif`, `confidence.tif`, `probabilities.tif`, `inference.json` |

Maps directly to existing Stage 2.7 outputs. No alternate prediction format.

## Relationship to Prior Stages

| Stage | Integration |
|-------|-------------|
| 2.7 | `InferenceRequest.to_inference_config()` |
| 2.8 | `BatchInferenceRequest.to_batch_config()` |
| 2.9 | Fingerprints, validation statuses, review semantics |

## Future Stage 3.1

Stage 3.1 can implement FastAPI (or similar) by:

1. Deserializing HTTP payloads into `InferenceRequest` / `BatchInferenceRequest`
2. Calling `validate_*()` and `can_serve_prediction()`
3. Invoking existing Stage 2.7/2.8 runners
4. Returning `InferenceResponse` / `BatchInferenceResponse`
5. Attaching `ProvenanceRecord` to responses

No changes to ML contracts should be required.

## Known Limitations

- No HTTP server, auth, queues, or cloud deployment
- Service validation is an early boundary; Stage 2.7 deep validation still applies at execution
- Scientific gate policies are configuration-driven, not domain-specific rules

## Package Location

`model/src/ssri_model/service/`
