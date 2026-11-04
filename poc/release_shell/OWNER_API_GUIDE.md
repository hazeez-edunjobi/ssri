# Non-developer API guide (release shell)

## Does a full UI exist?

**Partial.** `/training/operator` supports classic Stage 2.5 create → upload → validate → train → promote, plus a **Known Limitations** panel. It does **not** yet call `/api/v1/release-shell/*`, show the PASS/WARN/FAIL shell validation report, multi-seed evaluation, or gate statuses.

Until that UI is wired, use these endpoints (e.g. with Postman, Bruno, or curl).

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
   Poll `GET /api/v1/jobs/{job_id}` until `completed` or `failed`.

5. **Evaluation report**  
   `GET /api/v1/training/models` → find `model_id` / `checkpoint_path`  
   `GET /api/v1/release-shell/models/{model_id}/evaluation`  
   Read per-seed results and gate strings (`evaluated` / `trained, no demonstrated skill beyond slope` / `trained, unconfirmed across seeds`).

6. **Assess**  
   Before any train: `POST /api/v1/assess` `{}` → `no_trained_model`.  
   After: `POST /api/v1/assess` with `checkpoint` + `features` and preferably `point` (lat/lon) for region check.  
   Each hazard returns `status`/`score`/`reason` — **score is null** unless gate is `evaluated` and inside training region.

## Must never

Insurance, engineering, safety, or emergency decisions. Scores are relative rankings only. Status stays NOT_VALIDATED.
