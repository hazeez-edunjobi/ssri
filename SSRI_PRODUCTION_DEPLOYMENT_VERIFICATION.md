# SSRI production deployment verification

Date: 2026-11-19  
Scope: confirm whether release `2f97d39` is deployed and operational.  
No application code changes, no refactors, no new features, no speculative fixes.

---

### 1. Executive verdict

**DEPLOYMENT INCOMPLETE**

Hosts for the frontend (Vercel) and API (Render) are live and expose release-level surfaces that match `2f97d39` (including `location_provenance` and platform model promote). The API is **not ready** for distributed execution: Redis ping fails and the queue is unconfigured, so `/api/v1/ready` returns **503**. Authenticated production smoke tests (sign-in, assess, CSV train, worker, promote, GEE acquisition) were **not** completed because no authorized production test credential was used in this verification.

---

### 2. Release identity

| Check | Result |
|-------|--------|
| Branch | `main` |
| Local HEAD | `2f97d39445eaf63e7824256b81d6a751af79b481` (`2f97d39`) |
| `origin/main` | Same SHA (after `git fetch`) |
| SHA match to expected release | **Yes** |
| Working tree | Tracked tree clean; untracked local scratch only (`poc/_tmp_handover_*.txt/json`) |
| Remote commit available | Yes — local/remote `main` aligned on the release tip |

**Note:** Neither the public API health payload nor OpenAPI advertises a git SHA. Commit identity of the *running* containers is therefore inferred from feature surface (see below), not from an explicit deploy build stamp.

---

### 3. Hosting and deployment

| Component | Hosting provider / target | Production URL | Status | Evidence |
|-----------|---------------------------|----------------|--------|----------|
| Frontend | **Vercel** | `https://ssri-gamma.vercel.app` | **Deployed (live)** | HTTP 200; SSRI marketing/login/dashboard routes; `server=Vercel`, `x-vercel-id` present |
| Backend API | **Render** (uvicorn behind Cloudflare) | `https://ssri-api.onrender.com` | **Deployed, not ready** | `/api/v1/health` → 200 `{"status":"ok","service":"ssri-inference"}`; `/api/v1/ready` → **503** |
| Worker | Expected Celery worker on Render / compose topology | No public URL | **NOT VERIFIED** | No worker health endpoint exercised; Redis/queue failure implies jobs cannot be processed in distributed mode |
| PostgreSQL | Render-side dependency of API | N/A (private) | **Connected (from readiness)** | Ready payload: `postgresql` `status=ok` `detail=connected` |
| Redis | Required for `distributed` mode | N/A (private) | **Unavailable** | Ready payload: `redis` `status=unavailable` `detail=ping_failed` |
| File storage | Persistent volume / object storage (config-dependent) | N/A | **NOT VERIFIED** | No authenticated upload/persist test |
| Google Earth Engine | Credential mount / env on API/worker | N/A | **NOT VERIFIED** | No live acquisition call; local repo has credential *paths* configured in `.env` and one file under `credentials/`, but production GEE access was not probed |

**Release-surface match (API OpenAPI on Render):**

- `AssessResponseBody.location_provenance` present  
- `POST /api/v1/platform/models/{model_id}/promote` present  
- `POST /api/v1/release-shell/datasets/{dataset_id}/labels/apply` present  
- Channel schemas `v1`/`v2` advertised via unauthenticated `GET /api/v1/release-shell/status` (`release_shell_enabled: false`)

**Release-surface match (frontend bundles on Vercel):**

- Production JS references `onrender.com` (API default), not `localhost:8000`  
- Bundle contains `location_provenance`  
- Promote-related strings present in JS  
- Supabase client markers present  

`https://ssri.vercel.app` responds but is **not** treated as the SSRI product frontend (historical note: unrelated site risk); verification used **`ssri-gamma.vercel.app`**.

---

### 4. Infrastructure

| Item | Observation |
|------|-------------|
| Execution mode | `distributed` (from ready details) |
| PostgreSQL | Connected |
| Redis | **ping_failed** |
| Queue | **unconfigured** |
| Readiness | **503** `SERVICE_NOT_READY` / `Infrastructure dependencies are not ready.` |
| Auth gate | `POST /api/v1/assess` without credentials → **401** `AUTHENTICATION_REQUIRED` |
| CORS | OPTIONS from `https://ssri-gamma.vercel.app` → allow-origin exactly that origin; methods GET/POST/OPTIONS; credentials allowed |
| Release shell flag | Public status reports **disabled** (`release_shell_enabled: false`) — appropriate default |
| Swagger | `/docs` and `/openapi.json` publicly reachable |
| Debug | Not directly readable from public endpoints; no evidence of client-driven demo mode in this probe |

Local configuration files (presence only; values not printed): `.env`, `frontend/.env.local`, `credentials/` exist on the developer machine. That does **not** prove the same secrets are installed on Render/Vercel.

---

### 5. Production test results

| # | Test | Result | Notes |
|---|------|--------|-------|
| 1 | Open production frontend | **PASS** | `https://ssri-gamma.vercel.app` 200 |
| 2 | Sign in with authorized test account | **NOT VERIFIED** | Login UI present; no production test account used |
| 3 | Dashboard / model-management pages load | **PASS** (anonymous shell) | `/dashboard`, `/models`, `/training`, `/shell`, `/workspace`, `/login` return 200 HTML; authenticated app behaviour not verified |
| 4 | Frontend communicates with production API | **PASS** (static/config) | Bundles hard-reference `onrender.com`; CORS allows the Vercel origin. Live authenticated XHR not verified |
| 5 | Submit assessment request | **NOT VERIFIED** | Blocked by authentication without a production API key / session |
| 6 | Coordinate provenance in response | **NOT VERIFIED** (runtime) | Schema + frontend code present; no authenticated assess response captured |
| 7 | Upload labelled client CSV (test dataset) | **NOT VERIFIED** | Requires auth + ready storage/worker path |
| 8 | Submit training job | **NOT VERIFIED** | Redis/queue not ready |
| 9 | Worker processes job | **NOT VERIFIED** | Infrastructure not ready; no worker probe |
| 10 | Promote resulting model | **NOT VERIFIED** | Route exists in OpenAPI; no authenticated call |
| 11 | Assess with promoted model | **NOT VERIFIED** | Depends on 5–10 |
| 12 | Persist uploads/checkpoints across restart | **NOT VERIFIED** | No safe restart test performed |
| GEE / live DEM sampling | **NOT VERIFIED** | Distinguish: geometric provenance code is deployed; live raster acquisition not proven |
| Known-coordinate live grid sampling | **NOT VERIFIED** | Would require auth + live acquisition enabled + healthy stack |

---

### 6. Blockers and warnings

#### Genuine deployment blockers

1. **Redis unavailable / queue unconfigured** — API readiness fails in `distributed` mode; training/job workflows cannot be considered operational.  
2. **No authenticated production smoke** completed — assess, CSV train, promote, and worker execution remain unproven on the hosted environment.  
3. **No explicit deploy SHA stamp** on the running service — cannot cryptographically prove the container is exactly `2f97d39` (only feature-surface equivalence).

#### Warnings (not immediate blockers for “hosts exist”)

1. Public `/docs` / OpenAPI exposure.  
2. Unauthenticated `GET /api/v1/release-shell/status` returns product limitations metadata (shell remains disabled).  
3. Worker process health is opaque from outside the host.  
4. GEE/OpenTopography production enablement unknown.  
5. Historical alternate Vercel hostname (`ssri.vercel.app`) should not be used as the product URL.

---

### 7. Required next actions

1. Repair **Redis** connectivity (and Celery broker/result backend) on the Render API/worker so `/api/v1/ready` returns ready.  
2. Confirm a **worker** process is running against the same Redis/Postgres and shared output storage.  
3. Supply an authorized **production test** API key and/or Supabase test user (do not commit secrets) and re-run the smoke list in §5.  
4. Optionally add a non-secret **build/commit** identifier to health/ready responses so future verification can pin the exact SHA.  
5. After Redis is healthy, verify one labelled **synthetic** CSV train → promote → assess cycle and one authenticated assess with `location_provenance`.  
6. Only if live AOI is required for the demo: confirm GEE/OpenTopo credentials on the production API/worker and test one known coordinate with live acquisition (not geometric-only).

Wait for approval before applying any configuration or code changes.

---

### 8. Final recommendation

**SSRI is not ready for a client demonstration that depends on training jobs, workers, or authenticated assessment on the current hosted stack.**

The marketing/login frontend and API process are online, and their public contracts strongly match release `2f97d39`, but the service reports **not ready** (Redis/queue), and critical authenticated workflows were not verified. Fix Redis/queue and complete an authenticated smoke pass before scheduling a production client demo.

---

### Appendix — probe summary (no secrets)

```text
GET  https://ssri-api.onrender.com/api/v1/health  → 200 ok
GET  https://ssri-api.onrender.com/api/v1/ready   → 503 redis ping_failed, queue unconfigured; postgres ok; mode=distributed
POST https://ssri-api.onrender.com/api/v1/assess  → 401 AUTHENTICATION_REQUIRED
OPTIONS assess (Origin: ssri-gamma.vercel.app)    → 200 CORS allow-origin exact match
GET  https://ssri-api.onrender.com/api/v1/release-shell/status → 200 shell disabled
GET  https://ssri-gamma.vercel.app[/login|/dashboard|/training|/models|/shell|/workspace] → 200
Frontend JS: onrender.com present; location_provenance present; localhost:8000 absent
```
