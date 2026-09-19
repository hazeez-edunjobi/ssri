# Stage 2.8 — Deployment & Batch Inference Orchestration

Stage 2.8 adds a production-oriented orchestration layer on top of the accepted
Stage 2.7 offline inference pipeline. It coordinates multiple AOI inference jobs,
persists batch manifests, supports resume, and exposes a CLI.

## Architecture

```
jobs.json
    │
    ▼
load_jobs_file() ── validate all JobSpec entries upfront
    │
    ▼
BatchRunner.run()
    ├── validate_job_inference_setup()  (Stage 2.7 contracts)
    ├── initialize / resume batch_manifest.json
    └── for each job (max_workers=1):
            should_skip_job()? ──► SKIPPED
            else run_inference() ──► isolated output dir
    │
    ▼
batch_manifest.json (atomic writes)
```

Modules under `ssri_model.orchestration`:

| Module | Responsibility |
|--------|----------------|
| `config.py` | `JobSpec`, `BatchConfig`, `BatchJobsFile` |
| `jobs.py` | Validation, jobs.json loading, job ID sanitization |
| `manifest.py` | `batch_manifest.json` persistence (atomic) |
| `resume.py` | Artifact verification and resume decisions |
| `status.py` | `get_batch_status()`, `summarize_batch()` |
| `runner.py` | `BatchRunner`, `BatchResult`, `JobResult` |
| `cli.py` | `run`, `status`, `resume` commands |

Stage 2.7 `run_inference()` is reused directly — the orchestration layer does not
duplicate inference logic.

## Job Format

Each job requires:

```json
{
  "job_id": "aoi-001",
  "checkpoint": "/models/best.pt",
  "features": "/datasets/aoi-001/feature_stack.npy",
  "manifest": "/datasets/aoi-001/manifest.json",
  "statistics": "/datasets/aoi-001/statistics.json"
}
```

Optional fields: `output_dir`, `inference_config`, `description`, `metadata`.

## Batch Format (`jobs.json`)

```json
{
  "batch_id": "ssri-demo-001",
  "jobs": [
    { "job_id": "aoi-001", "...": "..." },
    { "job_id": "aoi-002", "...": "..." }
  ]
}
```

The entire batch is validated before any inference starts.

## Output Structure

```
output_root/
  batch_manifest.json
  jobs/
    aoi-001/
      prediction.tif
      confidence.tif
      probabilities.tif
      inference.json
    aoi-002/
      ...
```

Each job writes to an isolated directory under `jobs/<job_id>/`.

## Batch Manifest

`batch_manifest.json` tracks batch and job status:

- Job statuses: `pending`, `running`, `completed`, `failed`, `skipped`
- Batch statuses: `pending`, `running`, `completed`, `completed_with_errors`, `failed`

Manifest updates use atomic writes (`batch_manifest.json.tmp` → replace).

Every manifest includes:

```json
"scientific_validation_status": "NOT_VALIDATED"
```

## Resume Behavior

With `resume=True`:

1. Load existing `batch_manifest.json`
2. Verify artifacts for each job (`prediction.tif`, `confidence.tif`,
   `probabilities.tif`, `inference.json`)
3. Skip jobs with valid artifacts
4. Rerun failed, pending, or jobs with missing/corrupt artifacts

Running the same completed batch twice with `resume=True` performs no new
inference work (`skipped=N`, `completed=0`).

## Failure Semantics

| Setting | Behavior |
|---------|----------|
| `continue_on_error=True` (default) | Failed jobs do not stop remaining jobs |
| `fail_fast=True` | Stop scheduling new jobs after first failure |
| `overwrite=False` (default) | Raise error if batch output already exists |
| `overwrite=True` | Replace manifest and rerun all jobs |

Failed jobs record `error_type` and `error_message` in the manifest.

## CLI

```bash
# Run a batch
poetry run python -m ssri_model.orchestration run \
  --jobs jobs.json \
  --output-root outputs/

# Show status
poetry run python -m ssri_model.orchestration status \
  --manifest outputs/batch_manifest.json

# Resume
poetry run python -m ssri_model.orchestration resume \
  --manifest outputs/batch_manifest.json
```

Exit codes:

| Code | Meaning |
|------|---------|
| 0 | Success |
| 1 | Completed with errors |
| 2 | Invalid configuration |
| 3 | Fatal orchestration error |

## Status Reporting

```python
from ssri_model.orchestration import get_batch_status, summarize_batch

status = get_batch_status("outputs/batch_manifest.json")
print(status.summary.to_dict())
# {"total": 10, "pending": 0, "running": 0, "completed": 8, "failed": 1, "skipped": 1}
```

## Security Considerations

- Job IDs are sanitized; path traversal (`../`) is rejected
- Job output directories must live under `output_root/jobs/`
- No shell commands are executed from job definitions
- No secrets are stored in manifests or logs
- Checkpoints use existing trusted PyTorch loading only

## Scientific Validation Limitations

Successful batch execution means inference completed without technical errors.
It does **not** indicate geological accuracy or operational hazard validity.
All outputs remain `NOT_VALIDATED`.

## Examples

```python
from ssri_model.orchestration import BatchConfig, BatchRunner, JobSpec

jobs = [
    JobSpec(
        job_id="lagos-01",
        checkpoint="experiments/best.pt",
        features="data/lagos/feature_stack.npy",
        manifest="data/lagos/manifest.json",
        statistics="data/lagos/statistics.json",
    ),
]

runner = BatchRunner(BatchConfig(output_root="outputs/demo", device="cpu"))
result = runner.run(jobs, batch_id="demo-001")
print(result.to_dict())
```

## Known Limitations

- Default execution is single-process (`max_workers=1`)
- No distributed inference, queues, or cloud deployment
- Resume requires input paths stored in the batch manifest
- No automatic cleanup of partial outputs on failure

## Readiness for Stage 2.9

Stage 2.8 provides declarative batch orchestration with resume, manifest tracking,
and CLI entry points. Stage 2.9 can add service packaging (e.g. FastAPI), cloud
deployment, or parallel worker pools without changing Stage 2.7 inference contracts.
