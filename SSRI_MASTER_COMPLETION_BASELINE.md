# SSRI — Master Completion Baseline

**Date:** 2026-11-21  
**Mode:** Engineering closeout baseline (documentation)  
**Branch:** `main`  
**Positioning:** SSRI — See the ground before you build.

---

## Required final status

```text
Project engineering status: COMPLETE
Frontend deployment: VERIFIED
Backend deployment: VERIFIED
Scientific model validation: NOT_VALIDATED
Stage 2.5 data readiness: REAL FEATURES FOUND — LABEL ACQUISITION REQUIRED
Production promoted checkpoint: NOT_VERIFIED
Scientific production release: NOT QUALIFIED
Remaining work: Scientific data acquisition, label preparation, model training, independent evaluation and final model qualification.
```

**Evidence notes**

| Claim | Evidence |
|-------|----------|
| Frontend deployment VERIFIED | Vercel Production deployment for `b855cdb` recorded success (`SSRI_FRONTEND_PREFLIGHT_RELEASE_REPORT.md`; alias `https://ssri-gamma.vercel.app`) |
| Backend deployment VERIFIED | Production API `https://ssri-api.onrender.com` documented live (`GET /api/v1/health` → 200); engineering tip pushed to `main` / tag `ssri-completed` → `5d2e0cb` |
| Scientific model validation | Remains `NOT_VALIDATED` — no independent scientific qualification |
| Stage 2.5 data readiness | `SSRI_STAGE25_TRAINING_DATA_READINESS_REPORT.md` |
| Production promoted checkpoint | `NOT_VERIFIED` — no durable promoted Stage 2.5 weights confirmed on Render |
| Scientific production release | **NOT QUALIFIED** — feature data alone is not scientific validation |

This baseline does **not** treat passing CI, synthetic training, or feature inventories as scientific completion.

---

## 1. Engineering vs scientific completion

### Engineering completion (COMPLETE)

Implemented platform (repo + deployment history as evidenced):

- Next.js frontend (`frontend/`)
- FastAPI backend (`ssri_model.api.app:app`, `/api/v1`)
- Authentication and authorization (`SSRI_AUTH_*`, Supabase platform profiles)
- Assessment workflows and checkpoint resolution (active registry / operator paths; 13-vs-16 channel guard)
- Training job and model registry infrastructure
- Postgres, Redis and Celery distributed execution (`infra/docker-compose.yml`, worker `ssri.execute_job`)
- Recovery and operational reliability mechanisms (as implemented in stack)
- Geological dataset catalogue and offline schema-v2 feature application (not live score drivers)
- Product capabilities for **subsidence**, **landslide**, and **sinkhole** (product surface; science pending)
- Production frontend and backend deployment history (Vercel / Render)
- Automated CI verification (GitHub Actions)

Only production-verified where evidence supports the claim (see status table above). Live assess still requires a promoted 13-channel Stage 2.5 checkpoint on durable storage.

### Scientific completion (NOT COMPLETE)

**Scientific model validation: NOT_VALIDATED**

Remaining scientific work:

1. Acquire authoritative **subsidence** ground-truth inventories.  
2. Acquire authoritative **sinkhole** ground-truth inventories.  
3. Obtain suitable **landslide** labels compatible with Stage 2.5 three-class semantics (USGS binary/pseudo-absence is not sufficient as-is).  
4. Acquire an **African** independent labelled holdout.  
5. Co-register verified labels to compatible **13-channel** feature stacks.  
6. Establish **spatially independent** train / validation / test partitions.  
7. Train and evaluate the model.  
8. Document scientific metrics, limitations and independent validation.

Keep the current **13-channel** live inference contract. Do **not** promote synthetic checkpoints or incompatible 16-channel checkpoints. Feature datasets do **not** mean the model is scientifically validated.

---

## 2. Stage 2.5 data readiness (authoritative)

Source: `SSRI_STAGE25_TRAINING_DATA_READINESS_REPORT.md`

| Finding | Status |
|---------|--------|
| Verdict | `REAL FEATURES FOUND — LABEL ACQUISITION REQUIRED` |
| Genuine feature families | **2** — USGS FeatureStacks CONUS; WGM2012/EMAG2 geophysics |
| Verified Stage 2.5 three-class label datasets | **0** |
| Subsidence | **NOT READY** |
| Landslide | **PARTIAL** — USGS binary/pseudo-absence; incompatible with Stage 2.5 0/1/2 contract as-is |
| Sinkhole | **NOT READY** |
| African / independent labelled holdout | **NOT FOUND** |

---

## 3. Authoritative subsystems

| Subsystem | Authority | Deprecated / incompatible |
|-----------|-----------|---------------------------|
| API | `model/src/ssri_model/api/app.py` → `/api/v1` | Root `api/` Stage-0 |
| Worker | `ssri_model.worker` Celery `ssri.execute_job` | Root `worker/` scaffold |
| Assess model | `SSRIModel` Stage 2.5; `CHANNEL_COUNT=13` | Foundation multitask ≠ assess; schema-v2 16-ch not live |
| Frontend | `frontend/` Next.js | — |
| Compose | `infra/docker-compose.yml` | — |
| Geological | `ssri_model.geological` + offline apply | Conditioning ≠ hazard labels; not live scores |

Engineering milestone tag: **`ssri-completed`** → `5d2e0cb` (engineering only; not scientific certification).

---

## 4. Scientific / ML posture

- Stage 2.5 contract: `ml/constants.py`, `ml/labels.py` (subsidence=0, landslide=1, sinkhole=2, nodata=−1).  
- Local Stage 2.5 `best.pt` candidates identified previously are **synthetic / rehearsal** (`SSRI_STAGE25_CHECKPOINT_DISCOVERY_REPORT.md`).  
- Schema-v2 defined for offline conditioning; Phase 6 live 16-channel assess remains **BLOCKED**.  
- Historical research scorecard (`docs/SSRI_COMPLETION_SCORECARD.md`): AUC/ECE gates failed / incomplete — not production science proof.

---

## 5. Priority remaining work (scientific programme)

1. Label acquisition for all three hazards under Stage 2.5 semantics.  
2. African independent holdout.  
3. Co-registered 13-channel FeatureStacks + spatial splits.  
4. Train / evaluate with honest metrics; keep `NOT_VALIDATED` until independent qualification.  
5. Durable shared storage for future real checkpoints (do not assume Render Free durability).  
6. Only then consider production promotion of a real 13-channel Stage 2.5 checkpoint.

---

*Engineering milestone closed. Scientific validation and scientific production release remain open.*
