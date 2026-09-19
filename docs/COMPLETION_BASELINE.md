# SSRI Completion Baseline

**Generated:** 2026-09-08  
**Source:** repository inspection + prior PRD gap analysis  
**Status at start of master completion:** `RESEARCH READY — LIVE PIPELINE VERIFIED` / `SCIENTIFIC_VALIDATION=NOT VERIFIED`

## What exists and is verified (engineering)

| Area | Evidence |
|------|----------|
| 13-channel FeatureStack | `feature_engineering.py` CHANNEL_ORDER; live stacks e.g. `(13,H,W)` |
| GEE Sentinel-2 | `gee_client.py` QA60 mask + median; live acquisition |
| OpenTopo COP30 | `topography.py`; min bbox pad ≥500 m |
| Gravity WGM2012 (not EIGEN-6C4) | Lagos GeoTIFF under `data/geophysics/` |
| Magnetics EMAG2v3 | Lagos GeoTIFF |
| U-Net SSRIModel | 13→3-class segmentation; default dropout 0.0 |
| Trainer / eval / scientific packages | Synthetic tests pass (~583) |
| Assess API | `POST /api/v1/assess` sync |
| Dashboard | MapLibre, coords, modal |
| Fixture checkpoint gate | `checkpoint_identity.py` fail-closed |

## Synthetic / fixture only

- E2E checkpoint `/data/outputs/e2e-job/checkpoint.pt` (`dataset_manifest.name=e2e`)
- All `Trainer.fit` CI paths use synthetic tiles
- Domain similarity uncalibrated without centroid file

## Missing (PRD science)

- USGS / BGS / IFFI labelled source data on disk
- African labelled target evaluation set
- DANN / GRL / domain-adversarial training
- Real foundation checkpoint `models/ssri-foundation-v1.pt`
- Measured AUC / ECE / transfer / latency gates
- SHAP (gradients used instead)
- Multi-task PRD heads (landslide / subsidence / **liquefaction**)
- Canonical sample schema + ingest pipelines

## PRD deviations already known

| PRD | Repo |
|-----|------|
| liquefaction | sinkhole |
| EIGEN-6C4 | WGM2012 |
| `/v1/assess` | `/api/v1/assess` |
| DANN | absent |

## Blockers at baseline

1. `TRAINING_DATA_NOT_AVAILABLE` — no hazard `label.tif` / source inventories mounted  
2. BGS/IFFI may require registration/license beyond automated fetch  
3. Liquefaction inventories for Africa are sparse / may be PUBLIC_DATA_NOT_FOUND  

## Exact key paths

- Model: `model/src/ssri_model/`
- Frontend: `frontend/`
- Infra: `infra/docker-compose.yml`
- Data on host: `data/geophysics/` only
- Docs: `docs/production_qualification.md`, `docs/model_card.md`, `docs/SSRI_MASTER_COMPLETION_PROMPT.md`
