# SSRI — Final Local Acceptance Report

**Date:** 2026-11-24  
**Mode:** Local verification only (no commit / push / deploy / retrain)  
**Git HEAD:** `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` (`main`, ahead 1 of origin)  
**Checkpoint:** `ssri-model-e7af3afcd0` SHA256 verified `d912027e…e5d004`  
**Companion:** `SSRI_FINAL_PRODUCT_COMPLETION_REPORT.md`

---

## Acceptance checks

| Check | Result |
|---|---|
| Preserve uncommitted FE remediation (F-01/F-03/F-04) | **PASS** |
| Preserve Abeokuta evidence artefacts | **PASS** |
| Active checkpoint unchanged | **PASS** (SHA256 match) |
| 13-channel inference contract unchanged | **PASS** |
| Assessment history UI (`/assessments`, `/assessments/[id]`) | **PASS** — browser list + detail |
| History API pagination | **PASS** — `limit`/`offset`/`has_more` (e.g. total 7) |
| Backend `test_production_gate` + `test_assess_history` | **PASS** — 16 passed |
| Backend geological suites (prior) | **PASS** |
| Frontend `npm test` | **PASS** — 94 passed |
| Assessments eslint + `tsc --noEmit` | **PASS** |
| Frontend `npm run build` | **PASS** — includes `/assessments` routes |
| API `GET /api/v1/health` | **PASS** — ok |
| API `GET /api/v1/ready` | **PASS** — ready (Postgres/Redis/queue ok; model NOT_VALIDATED) |
| `GET /api/v1/assess/history` | **PASS** |
| `GET /api/v1/geological/conditioning-factors` | **PASS** |
| Geological datasets catalogue | **PASS** — HTTP 200 |
| Abeokuta candidate lineaments | **PASS** — 72 candidates preserved |
| Docker Postgres / Redis | **PASS** — healthy |
| Celery worker | **PASS** — running on `ssri_jobs` |
| Frontend `:3000` | **PASS** |
| Staging production-gate subset (R-09) | **PASS** (code + tests) |
| Lease recovery staging default (R-10) | **PASS** (code + tests; prod still opt-in) |
| Product-path `safe_torch` loads (R-11) | **PASS** |
| CORS DELETE allowance | **PASS** |
| Real subsidence validation metrics | **FAIL / blocked** — missing ground truth (expected) |
| Production readiness | **Not claimed** |

---

## Abeokuta assessment continuity

Historical evidence IDs remain under `data/outputs/assessments/`. History UI and API surface prior scores (example detail `assess-7dfc19ea9b27c4b7`: subsidence ≈ 58.2%, landslide ≈ 52.7%, sinkhole ≈ 49.2%, Low confidence tiers). Checkpoint SHA in notes matches active registry. No retrain and no checkpoint swap.

Candidate lineament layers remain **context / analytics only** (`used_in_inference=false`).

---

## Infrastructure

| Component | Observation |
|---|---|
| FastAPI | Running with history + geological routes; ready |
| Frontend :3000 | Dev server + production build both verified |
| PostgreSQL / Redis | Docker healthy |
| Celery worker | Solo pool running |
| Lease recovery | Staging default-on; production requires explicit enable + approval |

---

## Scientific honesty gates

- Scores remain relative rankings / NOT_VALIDATED.  
- TMI Z not treated as overburden.  
- Candidates not labelled as faults.  
- No fabricated ground-truth metrics.  
- History UI does not invent missing API fields.

---

## Acceptance decision

**Local software acceptance: READY WITH DOCUMENTED LIMITATIONS**  
**Assessment history acceptance: PASS**  
**Ops R-09/R-10/R-11 (local/product path): PASS with production opt-in caveats**  
**Scientific validation acceptance: NOT VALIDATED (blocked by missing real subsidence inventory)**  
**Lineament processing acceptance: READY WITH DOCUMENTED LIMITATIONS (candidates only)**  
**Production: NOT VALIDATED — await approval; do not deploy from this pass**
