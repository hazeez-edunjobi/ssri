# SSRI — Presentation Demo Experience Report

**Date:** 2026-11-21  
**Scope:** Polished local presentation experience on existing `SSRI_DEMO_MODE`  
**Git:** no commit / push / deploy performed  

---

## 1. Executive summary

The existing server-side demo provider was expanded into a Nigeria sample-scenario catalogue with honest **Illustrative Demonstration** disclosures, a 15-second simulated assessment loading experience, and a dashboard scenario picker. Live Stage 2.5 inference, checkpoint validation, scientific validation status, and production env files were not weakened or promoted.

| Capability | Status |
|------------|--------|
| 15s staged loading UX (demo mode only) | **Done** |
| Nigeria sample catalogue (10 cities, 24 scenarios) | **Done** |
| Scenario picker on `/dashboard` | **Done** |
| Report / modal illustrative disclosure | **Done** |
| Demo/live isolation (no checkpoint bypass in live mode) | **Verified** |
| Demo results not persisted as production assessments | **Verified** |

---

## 2. Files changed

### Backend
| Path | Change |
|------|--------|
| `model/src/ssri_model/api/demo_assessment.py` | Expanded deterministic Nigeria catalogue + coherent CIs + conditioning samples |
| `model/src/ssri_model/api/routes/demo.py` | **New** `GET /api/v1/demo/scenarios` (404 when demo off) |
| `model/src/ssri_model/api/app.py` | Mount demo router |
| `model/src/ssri_model/api/routes/assess.py` | Optional `demo_scenario_key` (demo only); skip persist in demo |
| `model/src/ssri_model/api/schemas.py` | `demo_mode` on readiness (prior turn) |
| `model/tests/test_presentation_demo_catalogue.py` | **New** coherence / isolation tests |
| `model/tests/test_demo_mode_assess.py` | Disclosure assertion update |
| `model/tests/test_api_health.py` | Ready `demo_mode` coverage (prior turn) |
| `docs/SSRI_DEMO_MODE.md` | Operator notes for catalogue + no persist |

### Frontend
| Path | Change |
|------|--------|
| `frontend/lib/presentationDemo.ts` | Stages, progress helpers, wait helper |
| `frontend/lib/presentationDemo.test.ts` | Progress + grouping tests |
| `frontend/components/PresentationDemoProgress.tsx` | 15s staged progress UI + cancel |
| `frontend/components/PresentationScenarioPicker.tsx` | City/profile selector |
| `frontend/app/dashboard/page.tsx` | Picker wiring, duplicate-submit guard, parallel API + 15s wait |
| `frontend/components/AssessResultModal.tsx` | Demo progress, illustrative badge, susceptibility bars |
| `frontend/lib/api.ts` | `getDemoScenarios`, `demo_scenario_key` |
| `frontend/lib/assessRequest.ts` | Pass-through for `demo_scenario_key` |
| `frontend/lib/activeModelStatus.ts` | Illustrative disclosure copy |
| `frontend/lib/report.ts` | Downloadable report disclosure |

### Local config only
| Path | Change |
|------|--------|
| `.env` | `SSRI_DEMO_MODE=true` (local presentation; not production deploy config) |

---

## 3. Demo scenario catalogue

`GET /api/v1/demo/scenarios` returns **24** deterministic scenarios across:

| Location | Example scenario keys |
|----------|------------------------|
| Lagos | `elevated`, `moderate`, `low`, `mixed`, `coastal` |
| Abeokuta | `abeokuta-relief`, `abeokuta-stable` |
| Ibadan | `ibadan-mixed`, `ibadan-subsidence` |
| Port Harcourt | `ph-coastal`, `ph-low` |
| Benin City | `benin-balanced`, `benin-sinkhole` |
| Enugu | `enugu-escarpment`, `enugu-urban` |
| Calabar | `calabar-coastal`, `calabar-low` |
| Uyo | `uyo-mixed`, `uyo-sinkhole` |
| Jos | `jos-plateau`, `jos-moderate` |
| Abuja | `abuja-capital`, `abuja-hills`, `abuja-low` |

Each scenario includes: unique assessment id (stable hash), location name + coordinates, point/AOI type, three hazard scores, confidence tier (distinct from susceptibility), domain similarity, nested 80%/95% intervals, contributing Stage 2.5 channel names, summary, conditioning availability (unavailable ≠ zero; overburden is thickness not depth-to-bedrock), fixed timestamp, and report metadata notes.

**Honest framing:** scores are illustrative catalogue values for presentation contrast — **not** measurements or predictions for the named Nigerian locations.

---

## 4. Loading experience

When `presentationDemo` is true (from `/api/v1/ready`):

1. Click **Run assessment** (duplicate clicks blocked via in-flight ref).
2. Modal opens immediately with staged progress (not instant results).
3. Stages (15s total): validate AOI → prepare layers → subsidence → landslide/sinkhole → uncertainty → report.
4. API assess runs in parallel; UI waits for **both** API success and the 15s simulation.
5. Cancel aborts the wait and closes the in-flight lock; Escape / close cancels while loading.
6. Copy states this is a **presentation simulation**, not live satellite acquisition or inference.

Live mode (demo off) keeps the existing short “Acquiring features…” path — no 15s simulation.

---

## 5. Screens and routes

| Route | Demo behaviour |
|-------|----------------|
| http://localhost:3000/dashboard | Banner, scenario picker, 15s progress, illustrative report |
| http://localhost:3000/geological | Unchanged catalogue UI |
| `GET /api/v1/ready` | `demo_mode: true` |
| `GET /api/v1/demo/scenarios` | Catalogue (demo on only) |
| `POST /api/v1/assess` | Demo provider when `SSRI_DEMO_MODE=true` |

---

## 6. Test results

| Suite | Result |
|-------|--------|
| `poetry run pytest tests/test_demo_mode_assess.py tests/test_presentation_demo_catalogue.py tests/test_api_health.py -q` | **26 passed** |
| `cd frontend && npm test` | **66 passed** |

Covered: deterministic demo results, score/interval nesting, three hazards, missing geological handling, demo/live isolation, catalogue gating, no demo persist, progress stages, disclosure copy.

---

## 7. Exact local launch commands

```bash
# Terminal 1 — API (demo mode from repo-root .env)
cd model
poetry run uvicorn ssri_model.api.app:app --host 127.0.0.1 --port 8000

# Terminal 2 — UI
cd frontend
npm run dev
```

Open: **http://localhost:3000/dashboard**

Disable after presentation:

1. Set `SSRI_DEMO_MODE=false` in `.env`
2. Restart the API

---

## 8. Presentation script (suggested)

1. Show dashboard banner: **Illustrative Demonstration**.
2. Pick **Jos → Plateau relief landslide** (or Lagos elevated).
3. Click **Run assessment** — narrate the staged 15s workflow as a *simulated* product experience.
4. Walk hazard cards (subsidence / landslide / sinkhole), confidence vs susceptibility, conditioning availability.
5. Download HTML report — show the same illustrative disclosure.
6. Optionally switch to Abuja low vs Port Harcourt coastal to show contrasting profiles.
7. State clearly: platform remains research-ready / `NOT_VALIDATED`; no promoted production checkpoint was used.

---

## 9. Remaining limitations

- No real satellite acquisition, DEM download, or neural inference in demo mode.
- No GeoTIFF / spatial URL in demo responses (by design).
- Geological catalogue page may still be empty of uploaded datasets.
- 15s delay is UX-only; the API itself returns immediately.
- `SSRI_DEMO_MODE` must stay **false** for any scientific or client production assessment.
- Windows uvicorn `--reload` can leave stale listeners; prefer a clean start without reload for demos if port conflicts appear.

---

## 10. Safety checklist

| Guardrail | Status |
|-----------|--------|
| No synthetic checkpoint promotion | Preserved |
| No Stage 2.5 13-channel contract change | Preserved |
| No `scientific_validation_status` change | Preserved |
| Live mode still requires checkpoint | Verified |
| Demo payloads not persisted as production assessments | Verified |
| No fake GeoTIFF URLs | Verified |
| No production deploy / Git commit | Observed |
