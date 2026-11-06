# Non-developer API guide (release shell)

## UI first

Prefer **`/shell`** when `SSRI_RELEASE_SHELL=true`. If the page is incomplete or the API is offline, use the endpoints below (Postman, Bruno, or curl). Classic `/training/operator` does **not** call `/api/v1/release-shell/*`.

## Prerequisites

```text
SSRI_RELEASE_SHELL=true
SSRI_ASSESS_SOFTMAX=true
```

Start API: `poetry -C model run uvicorn ssri_model.api.app:app --port 8000`

## Step-by-step

1. **Create dataset**  
   `POST /api/v1/training/datasets`  
   Body: `{"name":"my-run","notes":"..."}` → save `dataset_id`.

2. **Upload ZIP**  
   `POST /api/v1/release-shell/datasets/{dataset_id}/upload`  
   multipart file field `file` = Stage 2.5 ZIP.

3. **Validate**  
   `POST /api/v1/release-shell/datasets/{dataset_id}/validate`  
   Read `validation.overall`, each check’s PASS/WARN/FAIL, and per-hazard ENABLED/DISABLED.  
   If `can_train` is false, **stop**.

4. **Train (3 seeds)**  
   `POST /api/v1/release-shell/jobs`  
   Body: `{"dataset_id":"...","epochs":3,"seeds":[42,43,44]}`  
   Poll **`GET /api/v1/jobs/{job_id}`** — response includes **`progress`**, **`result`** (evaluation + seed checkpoints when complete), and artifact paths.

5. **Evaluation report**  
   Prefer the job `result.evaluation` from step 4, or:  
   `GET /api/v1/training/models` → find `model_id` / `checkpoint_path`  
   `GET /api/v1/release-shell/models/{model_id}/evaluation`  
   Read per-seed results and gate strings (`evaluated` / `trained, no demonstrated skill beyond slope` / `trained, unconfirmed across seeds`).

6. **Select checkpoint**  
   `POST /api/v1/training/models/activate` with `{"model_id":"..."}`.

7. **Assess**  
   Before any train: `POST /api/v1/assess` `{}` → `no_trained_model`.  
   After: `POST /api/v1/assess` with `checkpoint` + `features` and preferably `point` (lat/lon) for region check.  
   Each hazard returns `status`/`score`/`reason` — **score is null** unless gate is `evaluated` and inside training region. Outside geography → `outside_training_region`.  
   Checkpoint channel schema must match the feature stack; mismatches name the missing channels.  
   Optional: `SSRI_PREVIEW_UNEVALUATED_SCORES=true` returns unevaluated preview scores (still NOT_VALIDATED).

### Local block size

```text
SSRI_RELEASE_SHELL_BLOCK_SIZE_KM=10   # or SSRI_RELEASE_SHELL_BLOCK_SIZE_DEG=...
```

When below 5°, responses include **local evidence only; not validated beyond this site**.

## Must never

Insurance, engineering, safety, or emergency decisions. Scores are relative rankings only. Status stays NOT_VALIDATED.
