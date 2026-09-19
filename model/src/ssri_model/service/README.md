# SSRI Service Contracts (Stage 3.0)

This package defines typed service contracts for future operational deployment
of the SSRI inference pipeline.

## Scope

Stage 3.0 provides **architecture and contracts only**:

- `ServiceConfig`
- `InferenceRequest` / `BatchInferenceRequest`
- `InferenceResponse` / `BatchInferenceResponse`
- `ProvenanceRecord`
- validation and scientific policy gates

There is **no HTTP server** in this package.

## Adapters

Requests adapt to existing APIs without modifying them:

- `InferenceRequest.to_inference_config()` → Stage 2.7 `InferenceConfig`
- `BatchInferenceRequest.to_batch_config()` → Stage 2.8 `BatchConfig`

## Scientific Validation

Operational execution status and scientific validation status are separate.
Successful inference never implies geological validation.

See `can_serve_prediction()` in `validation.py`.

## Documentation

Full architecture: `model/docs/STAGE_3_0_SERVICE_ARCHITECTURE.md`
