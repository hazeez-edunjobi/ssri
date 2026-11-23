# SSRI — Production Integrity Remediation: Commit, Release & Deploy

**Date (UTC):** 2026-11-21  
**Starting HEAD:** `d4a4a125ae2999f4a872b63971b4cc93f0e778de`  
**Resulting commit:** `d6e877a3d40e698ba9662a38ce652e51ba8a6131`  
**Message:** `fix: enforce production demo disablement and data integrity`  
**Push:** `origin/main` `d4a4a12..d6e877a` (PUSH_EXIT=0; no force-push)

**Targets:** Frontend `https://ssri-gamma.vercel.app` · Backend `https://ssri-api.onrender.com`

Scientific validation remains **NOT_VALIDATED**. No checkpoint was promoted or activated.

---

## Phase 1–2 — Scope committed

Staged **51 files** for the integrity remediation and tightly coupled geological/TMI preservation (so production FE/API stay coherent). **Not** staged: secrets/`.env`, `poc/_tmp_*`, prior audit markdown reports.

### Integrity-critical

| Area | Files |
|------|--------|
| `resolve_demo_mode` clamp | `model/.../api/config.py` |
| Ready / assess / demo routes | `health.py`, `schemas.py`, `assess.py`, `demo.py`, `demo_assessment.py`, `app.py`, `registry_status.py` |
| FE production gate | `frontend/lib/productionIntegrity.ts` (+ test) |
| Dashboard gating / clear results | `frontend/app/dashboard/page.tsx` |
| Marketing sample removal | `frontend/components/pages/PageHeader.tsx` |
| Compose defaults | `infra/docker-compose.yml`, `docker-compose.staging.yml` |
| Env docs | `.env.example`, `frontend/.env.local.example`, `docs/SSRI_DEMO_MODE.md` |
| Tests | `test_demo_mode_assess.py`, presentation catalogue, health, FE unit tests |

### Preserved (not hazard predictions)

Geological/TMI catalogue stack (`tmi.py`, geological service/routes/UI, fixtures, durability tests) included so catalogue work is not left half-deployed.

---

## Phase 3 — Verification (pre-push)

| Suite | Result |
|-------|--------|
| Backend demo + presentation + health + TMI + durability | **47 passed** |
| Frontend `lib/**/*.test.ts` | **68 passed** |
| Frontend `next build` | **Succeeded** |

---

## Phase 5 — Deployment outcomes

### Frontend (Vercel) — **PASS**

| Field | Value |
|-------|--------|
| Mechanism | Git-connected auto-deploy on `main` push |
| GitHub Deployment ID | `7970946920` |
| Creator | `vercel[bot]` |
| SHA | `d6e877a3d40e698ba9662a38ce652e51ba8a6131` |
| Status | **success** — “Deployment has completed” |
| Deployment URL | `https://ssri-dvanojwb9-hazeez-edunjobi.vercel.app` |
| Production alias | `https://ssri-gamma.vercel.app` |

No Vercel/Render CLI in PATH; existing GitHub→Vercel workflow used.

### Backend (Render) — **NOT VERIFIED / manual action likely required**

| Observation | Detail |
|-------------|--------|
| GitHub Deployments for `d6e877a` | **Only** Vercel Production entry — **no** Render deploy object |
| Live OpenAPI after push | Still **no** `/api/v1/demo/*`, **no** `ReadinessResponse.demo_mode`, **no** geological `/process` |
| Live `/api/v1/ready` | Still keys: `status`, `service`, `infrastructure` only |

**Conclusion:** Push alone did **not** evidence a Render API redeploy onto `d6e877a`. Operator must **manually Redeploy** the Render service tracking this repo (or confirm auto-deploy is enabled) so the process reloads production env with the new clamp + `demo_mode` on ready.

Credentials were not modified. No new deploy architecture introduced.

---

## Phase 6 — Post-deployment verification

### Backend

| Check | Class | Evidence |
|-------|-------|----------|
| `GET /api/v1/health` | **PASS** | **200** `{"status":"ok","service":"ssri-inference"}` |
| `GET /api/v1/ready` → 200 | **PASS** | Infrastructure ready (postgres/redis/queue ok) |
| `ready.demo_mode === false` | **NOT VERIFIED** | Field **absent** on live API (pre-`d6e877a` contract) |
| Model registry on ready | **NOT VERIFIED** | Not in live ready body; `/training/models/active` needs auth |
| `GET /api/v1/demo/scenarios` | **PASS** | **404** `{"detail":"Not Found"}` — catalogue not exposed |
| Assess unauthenticated | **PASS** | **401** `AUTHENTICATION_REQUIRED` — no hazard scores |
| Assess missing checkpoint (authed) | **BLOCKED** | No production credentials used |

### Frontend

| Check | Class | Evidence |
|-------|-------|----------|
| Sample result / Moderate / 48% / high confidence gone | **PASS** | `/about`,`/platform`,`/hazards`,`/developers` HTML: **no** `Sample result`; browser shows “Map assessment” / “Live hazard scores require a promoted Stage 2.5 model” / `NOT_VALIDATED` |
| Assessment Preview UI not activated in production | **PASS** (activation) | Production builds set `NODE_ENV=production` → `clientAllowsPresentationDemo()` false; scenario picker requires that gate |
| Presentation strings still in dashboard JS chunks | **PASS with note** | Bundles still contain `Assessment Preview` / `getDemoScenarios` from gated modules — **not** the same as UI activation |
| Invented assessment results on marketing | **PASS** | Replaced with honest unavailable copy |

### Scientific status

| Check | Class |
|-------|-------|
| Remains NOT_VALIDATED | **PASS** (copy + product contract; not claimed otherwise) |
| Live inference claimed | **Not claimed** — no promoted checkpoint verified |

---

## Remaining blockers

1. **Manual Render API redeploy** onto `d6e877a` so production exposes `demo_mode: false` on ready and the environment clamp / updated OpenAPI.
2. Authenticated missing-checkpoint assess smoke (**BLOCKED** without credentials).
3. Genuine Stage 2.5 production checkpoint promotion (out of scope; still blocked scientifically).

---

## Summary statuses

| Dimension | Status |
|-----------|--------|
| Software integrity (committed + tested) | **PASS** |
| Frontend production deployment | **PASS** (`d6e877a` on Vercel / `ssri-gamma`) |
| Backend production deployment | **NOT VERIFIED** — live API still pre-contract; Render redeploy needed |
| Genuine model inference availability | **NOT VERIFIED / unavailable to claim** |
| Scientific validation | **NOT_VALIDATED** |

**Bottom line:** Integrity changes are **committed and on `origin/main`**. **Frontend production** reflects them (sample scores removed). **Backend production** has not been confirmed on the new SHA — redeploy Render, then re-check `ready.demo_mode`.
