# SSRI — Demo Mode Disablement & Production Data Integrity

**Date:** 2026-11-21  
**HEAD (at start):** `d4a4a125ae2999f4a872b63971b4cc93f0e778de`  
**Scientific validation:** `NOT_VALIDATED` (unchanged)  
**Live assessment claim:** **Not claimed** — no genuine production checkpoint promoted.

---

## 1. Demo-data sources discovered

| Source | Path / mechanism | Disposition |
|--------|------------------|-------------|
| Presentation catalogue scores | `model/.../demo_assessment.py` + `SSRI_DEMO_MODE` | Kept for **development tests only**; forced off in production/staging |
| Demo scenarios API | `GET /api/v1/demo/scenarios` | 404 when demo off |
| Assess short-circuit | `routes/assess.py` demo branch | Inactive when `demo_mode=false` |
| Dashboard Assessment Preview UI | `dashboard/page.tsx`, scenario picker, 15s progress | Production builds never activate |
| Client opt-in bypass | `hasAssessmentModelAccess(..., presentationDemo)` | Only if presentation demo active (dev opt-in) |
| Marketing “Sample result” card | `PageHeader.tsx` fabricated Moderate / 48% / high confidence | **Removed** |
| Local `.env` `SSRI_DEMO_MODE=true` | Root `.env` | Set to **`false`** |
| Fixture/rehearsal checkpoints | `SSRI_ALLOW_FIXTURE_CHECKPOINTS` | Default **false** in Compose |
| Offline `.npy` / checkpoint override | Advanced operator options | Preserved for operators; not a silent mock fallback |
| MapLibre demotiles basemap | Style URL only | Not hazard scores; left as basemap fallback |
| Workspace counts | `/platform/me` | Already real records; empty shows 0 / “No activity yet” |
| Geological / TMI catalogue | `/geological` | **Preserved** (not demo data) |

There is **no** `NEXT_PUBLIC_*DEMO` flag that invents assessments. Fake scores entered only via server `SSRI_DEMO_MODE` + (formerly) automatic dashboard activation.

---

## 2. Demo features disabled / hardened

1. **Production/staging hard-disable** — `resolve_demo_mode()` forces `demo_mode=False` when `SSRI_API_ENVIRONMENT` is `production` or `staging`, even if `SSRI_DEMO_MODE=true`.
2. **Compose defaults** — `SSRI_DEMO_MODE=false`, `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false` on API; staging override sets both explicitly false.
3. **Local `.env`** — `SSRI_DEMO_MODE=false`.
4. **Frontend production gate** — `productionIntegrity.ts`: production Next builds never show Assessment Preview; development requires `NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO=true` **and** server demo mode.
5. **Misconfiguration notice** — if a production client sees `ready.demo_mode=true`, it warns and still refuses catalogue UI.
6. **Failed assess** — clears `result`; no mock substitute; unavailable copy when no promoted checkpoint.
7. **Marketing sample scores** — replaced with truthful “model required / NOT_VALIDATED” note.

---

## 3. Configuration changes

| File | Change |
|------|--------|
| `model/.../api/config.py` | `resolve_demo_mode`; clamp in `from_env` / `from_dict` / `__post_init__` |
| `infra/docker-compose.yml` | Explicit `SSRI_DEMO_MODE` / fixture defaults |
| `infra/docker-compose.staging.yml` | `SSRI_DEMO_MODE=false` |
| `.env` | `SSRI_DEMO_MODE=false` |
| `.env.example` | Documents hard-disable |
| `frontend/.env.local.example` | Documents opt-in flag (dev only) |
| `docs/SSRI_DEMO_MODE.md` | Rewritten for production integrity |

---

## 4. Frontend changes

- `lib/productionIntegrity.ts` (+ tests)
- `app/dashboard/page.tsx` — gated presentation demo; clearer unavailable messaging; clear results on failure
- `components/pages/PageHeader.tsx` — no fabricated sample hazard card
- `app/workspace/page.tsx` — show factual `0` when counts exist

---

## 5. Backend changes

- `APIConfig` production/staging demo clamp
- Assess path unchanged when demo off (still requires real checkpoint / live path)
- Demo modules **retained** for isolated development tests

---

## 6. Dashboard / map

- No scenario library in production builds
- No automatic mock assess on API failure
- Map remains AOI picker; gravity overlay stays visualization-only (not hazard prediction)
- Geological/TMI layers unchanged and not presented as hazard scores

---

## 7. TMI / geological preservation

- TMI validation/processing/provenance code paths untouched by this disablement
- Geological catalogue UI retained
- Regression: `tests/test_geological_tmi.py` included in verification set

---

## 8. Tests and results

| Suite | Result |
|-------|--------|
| `tests/test_demo_mode_assess.py` + presentation catalogue + health + TMI | **39 passed** (includes production/staging clamp + staging cannot serve demo assess) |
| Frontend `lib/**/*.test.ts` (incl. `productionIntegrity`) | **68 passed** |
| Frontend `next build` | **Succeeded** (TypeScript + static generation) |

Development demo tests remain usable with `SSRI_API_ENVIRONMENT=development` and `SSRI_DEMO_MODE=true`.

---

## 9. Production deployment verification

Operators should confirm after deploy:

1. `GET /api/v1/ready` → `demo_mode: false`
2. `GET /api/v1/demo/scenarios` → 404
3. `POST /api/v1/assess` without promoted model → error / unavailable (no catalogue scores)
4. Production frontend build does not show Assessment Preview / scenario picker
5. `scientific_validation_status` remains `NOT_VALIDATED`

Compose/staging now pin `SSRI_DEMO_MODE=false`. Restart API processes that previously loaded `SSRI_DEMO_MODE=true`.

---

## 10. Remaining unavailable capabilities

- **Live model inference** — pending a genuine compatible Stage 2.5 production checkpoint and promotion
- **Scientifically validated predictions** — still `NOT_VALIDATED`
- Assessment Preview walkthroughs — available only in **development** with explicit dual opt-in (server + `NEXT_PUBLIC_SSRI_ALLOW_PRESENTATION_DEMO`)

**Do not report successful live assessment until a genuine production checkpoint exists and real inference has been executed.**
