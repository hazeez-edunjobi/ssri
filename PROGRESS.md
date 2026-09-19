# SSRI Production Completion Progress

**Session start:** 2026-09-08  
**Goal:** Close Stage 3.4.5 audit gaps (Tracks A/B/C) without dressing engineering success as science.

## Assumptions

- No labeled training dataset exists under `data/` (only `data/geophysics/`). Confirmed at session start.
- Audit report lived in the prior chat session; `docs/STAGE_3_4_5_AUDIT_REPORT.md` was not in-repo at start (findings applied from that audit).
- Track A1 training cannot proceed without real labels; stop at that boundary (no fake checkpoint).

---

## Log

### 2026-09-08 — Session open

- Scoped Track A: `data/` contains only `geophysics/`; no labeled `datasets/`; no production `.pt` in git.
- Started Track B1/B2 (domain similarity gate + durable assess audit).
- Track C1: recovery existed under Compose profile `recovery` only.
- Track C2: gated integration tests require real Postgres/Redis.

### 2026-09-08 — Track B implemented

- **B1:** Removed hard-coded zero centroid from assess path. Domain similarity now requires `SSRI_DOMAIN_CENTROID_PATH` (non-zero `.npy`). Otherwise `domain_similarity_calibrated=false` and score is `null` (tier forced Low — conservative, not cosmetic).
  - Files: `model/src/ssri_model/api/domain_similarity.py`, `model/src/ssri_model/api/routes/assess.py`, `model/src/ssri_model/uncertainty/__init__.py`
  - Tests: `tests/test_domain_similarity.py`, `tests/test_api_assess_audit.py`, `tests/test_uncertainty.py` — **21 passed** (with related suites).
- **B2:** Assess responses now include `checkpoint_sha256`, dataset name/version, `is_fixture_checkpoint`; persist `assess_response.json`; fixture names refused in staging/production unless `SSRI_ALLOW_FIXTURE_CHECKPOINTS=true`.
  - Files: `model/src/ssri_model/api/checkpoint_identity.py`, assess route, frontend `lib/api.ts` + dashboard copy (“Model confidence … not hazard severity”).
- **Docs:** Executive section of `docs/production_qualification.md` updated so live Lagos is no longer falsely BLOCKED; still **not** production-validated.
- **Config:** `.env.example` + `infra/docker-compose.staging.yml` for recovery + published ports.

### 2026-09-08 — Track C verified

- **C1:** Staging overlay starts `ssri-recovery` with `SSRI_LEASE_RECOVERY_ENABLED=true`. Live DB path verified: seeded stale RUNNING job → `QUEUED` / `STALE_LEASE_RECOVERED` (`PASS_C1_C2_INLINE` in api container). Script: `model/scripts/verify_lease_recovery.py`.
- **C2:** `SSRI_INTEGRATION_TESTS=1` against live Compose Postgres/Redis — **2 passed** (`test_readiness_with_real_services`, `test_postgres_job_lifecycle`).

### 2026-09-09 — Master completion resume (USGS → foundation)

See authoritative log: `docs/IMPLEMENTATION_PROGRESS.md`.

- USGS v3 manually placed → **251,344** ingested.
- FeatureStack dataset v2: **80/80** real stacks (GEE DEM after OpenTopo 50/day limit).
- Foundation checkpoint `models/ssri-foundation-v1.pt`; test tile ROC-AUC **0.574** (gate 0.88 **not met**).
- Next master stage: Phase 3 African direct-transfer baseline (COOLR FeatureServer 404 blocker).


- Cannot train a real checkpoint or claim informative CIs without inventing data (forbidden).

### 2026-09-08 — Lagos InSAR scientific qualification (no training)

- Qualified DOI `10.7294/19738957` against SSRI contracts: **BENCHMARK-ONLY**.
- Semantics: continuous VLM (cm/yr) + building-collapse risk R0-R4 + collapse catalog — **not** `{0,1,2}` label.tif.
- License: dataset v1 **CC0 1.0**; paper **CC BY-NC 4.0**; confirm v2.
- Leakage: FeatureStack has no InSAR channels — OK if VLM stays external.
- `landslide` / `sinkhole`: still `PUBLIC_LAGOS_DATA_NOT_FOUND`.
- A1 **not** unblocked. Docs: `docs/dataset_candidates_report.md`, `docs/production_qualification.md` §18.


- Authored `docs/dataset_candidates_report.md`.
- SSRI classes confirmed: `subsidence`, `landslide`, `sinkhole` (flood is out of label set).
- Honest outcomes: **no strong public Lagos multi-hazard label set**; subsidence has **Partial** Lagos InSAR candidates (Ohenhen/Shirzaei); landslide/sinkhole lack adequate public Lagos/Nigeria inventories.
- Did **not** download/integrate data, change training code, or declare A1 unblocked.


- Rebuilt/restarted `ssri-api` + `ssri-worker` with staging overlay.
- Verified in container: `AssessResponseBody` includes identity/calibration fields; `resolve_domain_similarity` returns uncalibrated without centroid path.
- **Behavior change:** `SSRI_API_ENVIRONMENT=staging` and `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false` — assessments with `dataset_manifest.name=e2e` will now be **refused** until a real checkpoint exists or an explicit allow flag is set for a named qualification run.

### 2026-09-08 — Checkpoint + live Lagos qualification

- **Checkpoint commit:** `c13cac7` — qualified geophysics + scientific-data docs/tests (pre-live known-good).
- **GEE:** `GEE_INIT=OK` (SA `ssri-earth-engine@ssri-504721.iam.gserviceaccount.com`, project `ssri-504721`).
- **OpenTopo:** `OPENTOPO_DEM=OK` COP30 tiny Lagos bbox via dotenv helper (72×72, EPSG:4326, nodata -9999).
- **Live flags:** api/worker recreated with `SSRI_LIVE_ACQUISITION_ENABLED=true` and `SSRI_ALLOW_FIXTURE_CHECKPOINTS=true` (Compose host env; defaults unchanged in repo).
- **WBT blocker:** live assess hit `PermissionError` downloading WhiteboxTools into non-writable site-packages → fixed by installing binary in running containers + Dockerfile `download_wbt`; clearer `_get_whitebox` error / `SSRI_WHITEBOX_DIR` support.
- **ONE live Lagos assess:** `assess-8d74bea1a7b697af` HTTP 200; FeatureStack `(13,74,74)` COP30+GEE spectral+WGM2012/EMAG2v3; **fixture** checkpoint `e2e` sha256 `ff30ff00…`; `SCIENTIFIC_VALIDATION=NOT VERIFIED` unchanged.
- Verdict: **RESEARCH READY — LIVE PIPELINE VERIFIED** (not production; not scientifically validated).

### 2026-09-08 — Production-checkpoint readiness audit (no training)

- **Decision:** `TRAINING_BLOCKED` / `PRODUCTION_CHECKPOINT=BLOCKED`
- **Evidence:** `data/` contains only `geophysics/` (WGM2012/EMAG2v3 features). No `label.tif` / labelled dataset root / production `manifest.json` for hazards on disk. Test fixtures are synthetic only.
- **Pipeline:** Stage 2.2–2.9 training/eval/scientific machinery is present and unit-tested (**216 passed** readiness subset). Training entry is Python API (`Trainer` + `TrainingConfig`), not a dedicated CLI. Scientific CLI: `poetry run python -m ssri_model.scientific …`. Evaluation: `Evaluator` / `evaluate_checkpoint`.
- **Classes unchanged:** subsidence=0, landslide=1, sinkhole=2; flood not a label.
- **InSAR DOI 10.7294/19738957:** remains **BENCHMARK-ONLY** — no approved VLM→label protocol implemented.
- **Landslide / sinkhole:** `PUBLIC_LAGOS_DATA_NOT_FOUND`.
- **Partial-class research:** three-head architecture expects `{0,1,2}`; absent-class audits warn; no authorized partial-class production path.
- **Safety:** restored runtime `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false` under staging after engineering live-fixture run; `.env.example` defaults remain fail-closed.
- Live pipeline verdict unchanged: **RESEARCH READY — LIVE PIPELINE VERIFIED**.

### 2026-09-08 — Clean Docker WBT rebuild + concurrency fix + fixture live regression

- Clean `--no-cache` builds of **api** and **worker**; WBT binary present in both images without runtime install.
- Concurrent save flake: SQLite StaticPool thread-safety — fixed tests (`build_sqlite_file_job_store` + upsert semantics doc). Full suite **575 passed**.
- Live Lagos on clean API: fail-closed 400, then controlled fixture allow → `assess-886d57800cebbaf8` HTTP 200 — **LIVE PIPELINE VERIFIED USING FIXTURE CHECKPOINT**; fail-closed restored.
- Checkpoint gate unchanged: `TRAINING_DATA_NOT_AVAILABLE`.

### 2026-09-08 — EE pixel-limit tiling + dashboard coords/modal

- **Bug:** `sampleRectangle` failed for larger AOIs (`Too many pixels … Got 314070`).
- **Fix:** deterministic UTM tiling in `feature_engineering._export_ee_image_to_grid` (safe ≤250k px/tile); mosaic preserves grid/CRS/channels; absurd AOIs rejected with validation error.
- **Frontend:** manual lat/lon Locate + `AssessResultModal` after `/api/v1/assess` (fixture banner honest).
- **Tests:** `test_ee_sample_tiling.py`; full model suite **583 passed**; frontend `tsc` + `next build` OK; Playwright dashboard **8 passed** (after Chromium install; one mid-recreate flake re-run OK).
- **Staging large AOI:** HTTP 200 `assess-76b3187de114b6b0` on `(3.30–3.45, 6.45–6.60)`; FeatureStack 13ch EPSG:32631 @ 30 m; fixture allow restored to `false`.
- Verdict unchanged: **RESEARCH READY — LIVE PIPELINE VERIFIED**.

---

## Reporting template (end of session)




```
COMPLETED (verified):
- [B1] Domain similarity no longer uses hard-coded zeros; uncalibrated gated via domain_similarity_calibrated
  — evidence: model/src/ssri_model/api/domain_similarity.py; tests/test_domain_similarity.py (all-zero rejected); 21 related tests passed
- [B2] Checkpoint sha256 + dataset identity + fixture tag/refuse + assess_response.json persistence
  — evidence: model/src/ssri_model/api/checkpoint_identity.py; routes/assess.py; tests/test_api_assess_audit.py
- [B2 UI] Fixture banner + “Model confidence (not hazard severity)” + uncalibrated domain copy
  — evidence: frontend/app/dashboard/page.tsx; frontend/lib/api.ts
- [C1] Staging recovery service on + stale-lease DB recovery PASS
  — evidence: infra/docker-compose.staging.yml; ssri-recovery LEASE_RECOVERY_ENABLED=true; PASS_C1_C2_INLINE
- [C2] Gated integration tests against real Postgres/Redis
  — evidence: pytest tests/test_infrastructure_integration.py → 2 passed
- [Docs] production_qualification.md executive verdict corrected for live pipeline vs science gap
  — evidence: docs/production_qualification.md §1
- [Deploy] api/worker images rebuilt; new assess fields live in ssri-api
  — evidence: docker exec import AssessResponseBody fields; DomainSimilarityResult uncalibrated

PARTIALLY DONE:
- [C1 prod promotion] Staging Compose verified; no cloud/k8s cron beyond local `ssri-recovery`
- [B1 calibrated similarity] Gate works; no real reference centroid artifact yet (needs training-domain embeddings)

BLOCKED / NEEDS HUMAN DECISION:
- [A1] Real trained checkpoint + dropout>0 — no labeled dataset in-repo (`data/` = geophysics only)
- [A2] Hazard validation — blocked on A1 + ground truth + pre-declared thresholds + expert sign-off
- [DoD #4] Product/legal sign-off on end-user hazard scores — human only
- [Local demos] e2e fixture now refused under staging; set SSRI_ALLOW_FIXTURE_CHECKPOINTS=true only for explicit qualification, or use development without staging overlay

NOT STARTED:
- [A3 full] Full qualification rewrite after A1/A2 (executive section already corrected)
- Rollback / drift-monitoring plan for a production checkpoint (needs A1 first)
```

## Production readiness (honest)

**Engineering complete for Tracks B + C (local/staging Compose). NOT production-ready / NOT scientifically validated.**  
Missing A1/A2, calibrated domain centroid file, product/legal sign-off, cloud recovery scheduling, rollback/drift plans.
