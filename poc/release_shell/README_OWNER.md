# Owner guide — upload-and-train shell

For a **non-developer** operator. Branch only; nothing is merged or deployed by this work.

## What you can do

1. Upload a labelled Stage 2.5 ZIP  
2. Read a validation report (PASS / WARN / FAIL)  
3. Start training  
4. Read an automatic evaluation report (held-out blocks + slope baseline + gates)  
5. Run assess with the trained checkpoint  

Before any training, assess returns **`no_trained_model`**.

## Setup (once)

```bash
cd model
poetry install
set SSRI_RELEASE_SHELL=true
set SSRI_RELEASE_SHELL_BUFFER_KM=0
set SSRI_RELEASE_SHELL_MIN_TILES=4
set SSRI_RELEASE_SHELL_MIN_BLOCKS=4
set SSRI_RELEASE_SHELL_MIN_HELD_OUT=2
poetry run uvicorn ssri_model.api.app:app --reload --port 8000
```

Production defaults (without the MIN_* overrides) are **300 tiles / 8 blocks / 3 held out**.

## Step by step

1. `POST /api/v1/training/datasets` — create a dataset record  
2. `POST /api/v1/release-shell/datasets/{id}/upload` — upload ZIP  
3. `POST /api/v1/release-shell/datasets/{id}/validate` — read the report; **FAIL → do not train**  
4. `POST /api/v1/release-shell/jobs` — start training (progress via `/api/v1/jobs/{job_id}`)  
5. Open evaluation: `GET /api/v1/release-shell/models/{model_id}/evaluation`  
6. `POST /api/v1/assess` with `"checkpoint": "<path to best.pt>"`  

Demo ZIP: `templates/SYNTHETIC_stage25_template.zip` (fake data).

Broken ZIP demo: upload a zip missing `feature_stack.npy` → validation FAIL → training refuses.

## Full API guide (if UI is not enough)

See **`OWNER_API_GUIDE.md`** — the operator page covers classic training only; release-shell validate/train/eval uses `/api/v1/release-shell/*`.

## Must never be used for

Insurance, engineering design, safety-critical work, or emergency decisions. Scores are relative rankings only. Status stays **NOT_VALIDATED**.

See `LIMITATIONS.md`, `DEMO_SCRIPT.md`, and `MERGE_CHECKLIST.md` (orphan branches: DeepSlide 9, v3 slope index).
