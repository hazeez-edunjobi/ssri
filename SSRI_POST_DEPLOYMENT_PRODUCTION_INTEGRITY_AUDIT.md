# SSRI — Post-Deployment Production Integrity Audit

**Audit type:** Read-only (no config, registry, DB, or code changes)  
**Audit time (UTC):** 2026-11-21 ≈ 23:15–23:20  
**Claimed reference commit:** `d4a4a125ae2999f4a872b63971b4cc93f0e778de` (“Publish final SSRI repository updates”)

### Targets tested

| Role | URL |
|------|-----|
| Frontend | `https://ssri-gamma.vercel.app` |
| Backend | `https://ssri-api.onrender.com` |

### Critical scope note (deployment vs repository)

Local workspace HEAD is still `d4a4a12`, but **demo-mode disablement / productionIntegrity / PageHeader sample removal / TMI process routes exist as uncommitted local changes**, not as committed content under `d4a4a12`.

| Safeguard | In `d4a4a12` (committed) | On production deploy (observed) |
|-----------|--------------------------|----------------------------------|
| `ready.demo_mode` field | Present in newer local tree; **not** the simpler production schema | **Absent** from live `/api/v1/ready` |
| `GET /api/v1/demo/scenarios` | Present in local tree | **Not in production OpenAPI** → FastAPI `404 {"detail":"Not Found"}` |
| `resolve_demo_mode()` production/staging clamp | Local uncommitted only | **Not deployable until committed + released** |
| `productionIntegrity.ts` (prod FE never enables preview) | Local uncommitted only | **Not on Vercel** |
| PageHeader without “Sample result” | Local uncommitted only | **Deployed FE still shows Sample result** |

This audit reports **what production actually does today**, then separately notes gaps vs the intended disablement work.

---

## Check results

### 1. `GET /api/v1/ready`

| Sub-check | Status | Evidence |
|-----------|--------|----------|
| Endpoint reachable | **PASS** | HTTP **200** (cold start previously timed out once; retry succeeded) |
| `demo_mode: false` | **NOT VERIFIED** | Response keys are only `status`, `service`, `infrastructure`. Field **`demo_mode` is missing** — cannot confirm boolean false |
| Model registry availability | **NOT VERIFIED** (auth) / **NOT VERIFIED** (ready) | Ready payload has **no** `model_registry`. `GET /api/v1/training/models/active` → **401** `AUTHENTICATION_REQUIRED` without credentials |
| Scientific validation `NOT_VALIDATED` | **NOT VERIFIED** | Not present on ready body. No authenticated assess success to observe status. Prior product contract remains NOT_VALIDATED; **not re-proven from this live payload** |

**Safe ready excerpt:**

```json
{
  "status": "ready",
  "service": "ssri-inference",
  "infrastructure": {
    "mode": "distributed",
    "ready": true,
    "components": [
      {"name": "configuration", "status": "ok"},
      {"name": "postgresql", "status": "ok"},
      {"name": "redis", "status": "ok"},
      {"name": "queue", "status": "ok"}
    ]
  }
}
```

Also: `GET /api/v1/health` → **200** `{"status":"ok","service":"ssri-inference"}`.

---

### 2. `GET /api/v1/demo/scenarios`

| Sub-check | Status | Evidence |
|-----------|--------|----------|
| HTTP 404 | **PASS** | **404** twice |
| No scenario catalogue exposed | **PASS** | Body `{"detail":"Not Found"}`; OpenAPI lists **no** `/api/v1/demo/*` paths |

Interpretation: production does not expose a demo catalogue (good). This is because the **demo router is absent from the deployed OpenAPI**, not because a deployed `demo_mode=false` handler returned the newer “SSRI_DEMO_MODE is off” message.

---

### 3. Production assessment behaviour (no promote / no activate)

| Sub-check | Status | Evidence |
|-----------|--------|----------|
| Unauthenticated assess | **PASS** (no fabricated scores) | `POST /api/v1/assess` with Lagos point → **401** `AUTHENTICATION_REQUIRED` — no `hazard_profiles` |
| Invalid credentials + `demo_scenario_key` | **PASS** (no fabricated scores) | **401** `INVALID_CREDENTIALS` — not Assessment Preview / catalogue JSON |
| Assess without promoted checkpoint (authenticated) | **BLOCKED** | No production credentials used (read-only; do not expose secrets). Cannot complete authed missing-checkpoint path on live API |
| Does not return demo catalogue scores | **PASS** (within unauthenticated/invalid-auth probes) | No successful assess body with catalogue scores observed |

**Safe assess excerpts:**

```json
{"error":{"code":"AUTHENTICATION_REQUIRED","message":"Authentication is required.","details":{}}}
```

```json
{"error":{"code":"INVALID_CREDENTIALS","message":"Invalid authentication credentials.","details":{}}}
```

No checkpoint was registered, activated, or promoted during this audit.

---

### 4. Deployed frontend

| Sub-check | Status | Evidence |
|-----------|--------|----------|
| Assessment Preview / scenario selection absent on public dashboard shell | **PASS** (public surface) | `/dashboard` HTML: no hits for `Assessment Preview`, `Scenario library`. Dashboard JS chunk scan: **no** hits for those strings / `getDemoScenarios` / `demo_scenario_key`. Unauthenticated `/dashboard` redirects to login |
| Authenticated dashboard behaviour (clear results / no mock on API fail) | **BLOCKED** | Login required; no session used |
| Fabricated Moderate / 48% / high-confidence marketing card removed | **FAIL** | Still present on deployed marketing pages |

**Marketing sample-card evidence (FAIL):**

| URL | HTTP | Strings found in HTML |
|-----|------|------------------------|
| `/about` | 200 | `Sample result`, `Confidence: high`, `48%`, `Moderate` |
| `/platform` | 200 | same |
| `/hazards` | 200 | same |
| `/developers` | 200 | same |

Browser a11y snapshot on `/about` and `/platform` also exposed names: “Sample result”, “Landslide risk”, “Confidence: high”.

Local uncommitted `PageHeader.tsx` removes this card; **Vercel production has not received that change**.

---

### 5. Existing data functionality

| Sub-check | Status | Evidence |
|-----------|--------|----------|
| Workspace counts reflect actual records | **BLOCKED** | `/workspace` requires auth (`login?next=/workspace` pattern); no session |
| Geological catalogue accessible | **PASS** (route exists; auth-gated) | `/geological` → redirects to `login?next=%2Fgeological`. API `GET /api/v1/geological/datasets` → **401** without/invalid auth (not a public leak of datasets) |
| TMI datasets not presented as hazard predictions | **PASS** (public surface) / **NOT VERIFIED** (authed TMI UI) | No public page presented TMI as hazard scores. Production OpenAPI has geological CRUD but **no** `/process` or `/compatibility` TMI endpoints — deployed API predates local TMI process routes. Authed TMI review UI **not** exercised |

---

## Discrepancies: deployed vs intended disablement

1. **Production API schema is older** than the local integrity work: no `demo_mode` on ready, no demo router, no TMI process/compatibility routes in OpenAPI.
2. **Commit `d4a4a12` is not the disablement delivery** for productionIntegrity / `resolve_demo_mode` / sample-card removal — those remain **local uncommitted** relative to that HEAD.
3. **Vercel still ships the marketing Sample result** (Moderate / 48% / high confidence).
4. Ready **200 does not prove** model inference or scientific validation (infrastructure readiness only).

---

## Remaining production blockers

1. Commit, release, and redeploy backend + frontend integrity changes (or confirm an equivalent older deploy policy).
2. Authenticated verification of: missing promoted checkpoint → unavailable assess (no scores); workspace zero/empty states; geological/TMI operator flows.
3. Promote a **genuine** non-synthetic Stage 2.5 production checkpoint before claiming live inference.
4. Keep scientific status **NOT_VALIDATED** until independent validation exists.

---

## Summary statuses

| Dimension | Status | Notes |
|-----------|--------|-------|
| **1. Software integrity** (local implementation intent) | **PARTIAL / NOT DEPLOYED** | Disablement implemented locally (uncommitted); not what production serves for FE sample card / ready.demo_mode |
| **2. Production deployment integrity** | **MIXED** | Demo catalogue not exposed (**PASS**); marketing sample scores still live (**FAIL**); ready lacks `demo_mode` (**NOT VERIFIED**); authed paths (**BLOCKED**) |
| **3. Genuine model inference availability** | **NOT VERIFIED / UNAVAILABLE for claim** | No successful live assess; active model endpoint requires auth; no evidence of a promoted production checkpoint in this audit |
| **4. Scientific validation** | **NOT_VALIDATED (not contradicted)** | Ready does not assert validation; no evidence of validated science from this probe |

**Bottom line:** Production currently does **not** serve a demo scenario catalogue and does **not** return assessment scores to unauthenticated callers. It also does **not** yet reflect the full post-disablement frontend/backend safeguards (especially removal of marketing sample scores and explicit `demo_mode: false` on ready). **Do not claim successful live model inference or scientific validation from this audit.**
