# SSRI — Local Scientific & Application Completion Report

**Date:** 2026-11-23  
**Mode:** Implementation + local verification (no production deploy, no secret exposure, no Git commit unless requested)

---

## Classification summary

| Area | Status |
|---|---|
| Local API + Postgres + Redis + Celery worker | **PASS** |
| Shared local output root (`data/outputs`) | **PASS** |
| Offline Stage 2.5 assess (13-ch `.npy` → real inference) | **PASS WITH LIMITATIONS** (synthetic checkpoint/features) |
| Training job via Celery (1 epoch, synthetic Stage 2.5 dataset) | **PASS WITH LIMITATIONS** (synthetic data; `NOT_VALIDATED`) |
| Demo mode off / honesty of validation status | **PASS** |
| Async Stage 2.7 inference with incomplete CRS manifest | **PASS WITH LIMITATIONS** (correctly refused; permanent error no longer burned across retries) |
| Live AOI acquisition (GEE/OpenTopo) | **BLOCKED BY OWNER INPUT** (credentials present in `.env` but not re-verified end-to-end this session) |
| Genuine scientific production checkpoint | **BLOCKED BY OWNER INPUT** |
| Frontend unit tests | **PASS** (68/68) |
| Frontend lint | **PASS** (after `PresentationDemoProgress` fix) |
| Full model pytest | **PASS** (890 passed, 3 skipped earlier this session) |

Scientific status remains **`NOT_VALIDATED`** everywhere exercised. Synthetic artefacts are labelled as such.

---

## 1. Implemented changes

| Change | Path |
|---|---|
| Publish Postgres `5432` for hybrid host Poetry + Compose DB | `infra/docker-compose.yml` |
| Upsert hybrid local `SSRI_*` (+ legacy Celery/Redis host URLs) | `scripts/upsert_local_env.py` |
| Bootstrap/activate 13-ch Stage 2.5 registry copy (`NOT_VALIDATED`) | `scripts/bootstrap_local_stage25_registry.py` |
| One-command local stack starter | `scripts/start_local_stack.ps1` |
| Robust `.env` discovery for API | `model/src/ssri_model/api/app.py` |
| Worker loads `.env`; prefers `SSRI_*` broker over Docker DNS `redis` | `model/src/ssri_model/worker/celery_app.py` |
| Permanent inference input failures get distinct codes; not blindly requeued | `api/job_workers.py`, `infrastructure/retry.py`, `worker/tasks.py` |
| Frontend lint: avoid sync `setState` in inactive effect | `frontend/components/PresentationDemoProgress.tsx` |
| Retry unit tests extended | `model/tests/test_infrastructure_retry.py` |

---

## 2. Fixed defects

1. **Local API was running with `demo_mode=true` / incomplete readiness** — stale process / Docker `ssri-api` image; replaced with host Poetry stack reading repo `.env`.
2. **Missing hybrid env** — `.env` lacked `SSRI_DATABASE_URL`, `SSRI_EXECUTION_MODE`, `SSRI_API_OUTPUT_ROOT`, `SSRI_REDIS_URL` (Compose-oriented Stage-0 keys only).
3. **Celery worker connected to `redis://redis:6379`** — legacy `CELERY_BROKER_URL` Docker hostname; fixed via env upsert + explicit `broker_url` from `SSRI_*`.
4. **Compose Postgres not reachable from host** — added published port `5432`.
5. **Permanent async inference input errors retried 3×** — missing projection metadata now maps to `INFERENCE_INPUT_INVALID` and is not requeued.
6. **Frontend lint failure** in presentation demo progress component.

---

## 3. Scientific calculations

- Stage 2.5 **13-channel** contract preserved (`CHANNEL_NAMES` / `CHANNEL_COUNT`).
- Offline assess ran **real** `SSRIModel` CPU inference (MC dropout path) on a 13×128×128 stack — not demo placeholders.
- Notes explicitly reported `NOT_VALIDATED`, uncalibrated domain similarity, and heuristic ranking language.
- Async Stage 2.7 path **correctly refused** a training manifest lacking projection metadata (no invented CRS).
- No change to `NOT_VALIDATED`; no fabricated geospatial fill-ins.

---

## 4. Model / training / inference

| Workflow | Evidence |
|---|---|
| Registry bootstrap | `ssri-model-e7af3afcd0` activated under `data/outputs/training/models/` |
| Offline assess | `assessment_id=assess-46505c335f99b261`; response under `data/outputs/logs/assess_e2e.json` |
| Celery training | `job-eb16433185310291` **completed**; new model `ssri-model-0505e7ab14`; status `NOT_VALIDATED` |
| Live `/ready` | `demo_mode=false`, `checkpoint_available=true`, `scientific_validation_status=NOT_VALIDATED` |

---

## 5. API and worker

Verified locally:

- `GET /api/v1/health` → ok  
- `GET /api/v1/ready` → distributed; postgres/redis/queue ok; active model present  
- Celery connected to `redis://127.0.0.1:6379/0`  
- Training job queued → claimed → completed with checkpoint artefact  

---

## 6. Frontend

- `NEXT_PUBLIC_API_URL=http://localhost:8000` already set in `frontend/.env.local`
- Unit tests: **68 passed**
- Lint: **PASS** after progress-component fix
- Start UI: `cd frontend && npm run dev`

---

## 7. Tests executed

| Suite | Result |
|---|---|
| `cd model && python -m pytest -q` | **890 passed, 3 skipped** |
| `pytest tests/test_infrastructure_retry.py tests/test_worker_health.py tests/test_api_assess.py` | **14 passed** |
| `cd frontend && npm test -- --run` | **68 passed** |
| `cd frontend && npm run lint` | **PASS** (post-fix) |

---

## 8. Remaining blockers / owner inputs

1. **Real labelled Stage 2.5 training dataset** (13-channel stacks + labels, CRS/projection metadata for Stage 2.7 async inference).  
2. **Confirm live AOI** with owner GEE/OpenTopo credentials (`SSRI_LIVE_ACQUISITION_ENABLED=true` already in `.env`).  
3. **Replace synthetic active checkpoint** with owner-trained weights before any client scientific claim.  
4. Optional: schedule lease-recovery process (`docker compose --profile recovery` or `recovery` entrypoint).  
5. Domain centroid file for calibrated similarity (`SSRI_DOMAIN_CENTROID_PATH`) if required.

---

## 9. Local startup

```powershell
# From repo root (Docker Desktop running; Redis on :6379)
powershell -ExecutionPolicy Bypass -File scripts/start_local_stack.ps1

# Frontend
cd frontend
npm run dev
```

Shared artefacts: `data/outputs/` (Windows path written into `.env` as `SSRI_API_OUTPUT_ROOT`).

Stop Docker `ssri-api`/`ssri-worker` if they reclaim port 8000 after Docker Desktop restarts — the start script stops them.

---

## 10. Local acceptance testing (owner)

1. Confirm `http://127.0.0.1:8000/api/v1/ready` shows `demo_mode=false` and your intended active model.  
2. Upload real geological / training data via UI or `/api/v1/training` / `/api/v1/geological`.  
3. Train → activate → assess with offline `.npy` or live AOI.  
4. Treat all scores as **research-only / NOT_VALIDATED** until independent scientific validation.

### Offline assess smoke (already proven)

```powershell
# features: 13xHxW float32 .npy under a readable path
Invoke-RestMethod http://127.0.0.1:8000/api/v1/assess -Method POST -ContentType application/json -Body (@{
  request_id = "owner-1"
  features = "C:\path\to\feature_stack.npy"
  hazards = @("subsidence","landslide","sinkhole")
  mc_samples = 8
} | ConvertTo-Json)
```

---

## Honesty note

Local completion uses **synthetic** Stage 2.5 weights and tiles to prove the **application pathway**. That does **not** constitute geological field validation or a production scientific model.
