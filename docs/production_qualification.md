# SSRI Production Qualification Report

**Date of evidence collection:** 2026-09-08 (local timezone UTC+1 session)  
**Environment:** Windows 10 host + Docker Desktop (WSL2 Linux containers)  
**Authoritative application:** `model/` (`ssri_model.api` + Celery worker)  
**Frontend:** `frontend/` (Next.js + MapLibre dashboard)  
**Report method:** Fresh re-verification against the current repository and running stack. Prior report claims were not reused unless re-confirmed.

---

## 1. Executive Summary

### CURRENT QUALIFICATION VERDICT: **RESEARCH READY — LIVE PIPELINE VERIFIED**

**Updated 2026-09-08 (checkpoint + live qualification session):** After known-good commit `c13cac7`, GEE init, OpenTopography COP30 download, live acquisition (Compose host-env override), and **one** real Lagos `/api/v1/assess` succeeded end-to-end. That run used an **E2E fixture checkpoint** (`dataset_manifest.name=e2e`, `is_fixture_checkpoint=true`) with `SSRI_ALLOW_FIXTURE_CHECKPOINTS=true` for explicit engineering qualification under staging — **not** a production-trained model. Domain similarity remained uncalibrated. There is still **no labeled training dataset** and **no scientific hazard validation** in-repo.

```text
SCIENTIFIC_VALIDATION=NOT VERIFIED
```

| Dimension | Status | Why |
|-----------|--------|-----|
| **Engineering readiness** | **Research/demo + live pipeline OK** | Live FeatureStack + assess path works; fixture checkpoints tagged/refused by env; assess responses persist with checkpoint sha256 |
| **Operational readiness** | **PARTIALLY READY** | Staging Compose + recovery; live flag enabled only via controlled host-env recreate (defaults remain false) |
| **Scientific validation readiness** | **NOT READY** | No labelled Lagos three-class ground truth; InSAR DOI remains BENCHMARK-ONLY |
| **External-service readiness** | **VERIFIED this session** | `GEE_INIT=OK`; `OPENTOPO_DEM=OK` (COP30); live assess acquisition `dem=COP30` + spectral + WGM2012/EMAG2v3 |
| **Deployment readiness** | **NOT READY** | No cloud deployment; no production-trained checkpoint; no product/legal sign-off |

**Why not PRODUCTION READY:** Missing real trained checkpoint + informative uncertainty, calibrated domain centroid from a reference distribution, hazard validation against ground truth, and authority sign-off on end-user liability. See `PROGRESS.md`.

---

## 1b. Superseded claims (do not reuse)

The earlier statement in this report that live Lagos AOI is **BLOCKED** on GEE IAM is **out of date** as of the 2026-09-08 live qualification. Prefer `PROGRESS.md` and assessment acquisition manifests under `/data/outputs/assessments/` for current engineering evidence.

---

## 2. Current Architecture

### As implemented (verified from code + runtime)

```
GEE (spectral) + OpenTopography (DEM) + local geophysics GeoTIFFs
        ↓
FeatureStack (CHANNEL_ORDER, 13 channels, 30 m UTM target)
        ↓
DatasetBuilder / SSRIDataset
        ↓
SSRIModel
        ↓
Trainer / Evaluator
        ↓
Inference / Batch
        ↓
Scientific Validation  ← NOT VERIFIED (no labelled validation data in this run)
        ↓
FastAPI (ssri-api)
        ↓
Auth (optional; currently development defaults / auth not enabled in .env)
        ↓
JobService
        ↓
PostgreSQL + Redis + Celery worker   (distributed mode — VERIFIED ready)
        ↓
MinIO/S3 object storage (profile: storage)
        ↓
Frontend (Next.js) / MapLibre
        + GET /api/v1/layers/gravity  → GeoJSON preview (read-only)
```

### Component identity

| Component | Implementation | Current evidence |
|-----------|----------------|------------------|
| API | `ssri-api` container, port 8000 | healthy; `/api/v1/ready` → ready |
| Worker | `ssri-worker` Celery | healthy after rebuild; broker Redis |
| PostgreSQL | `ssri-postgres` | healthy; ready reports connected |
| Redis | `ssri-redis` | healthy; queue reachable |
| MinIO/S3 | `ssri-minio` ports 9000–9001 | healthy; `MINIO_S3=OK` via `127.0.0.1:9000` |
| Frontend | `npm run dev` on host :3000 (Compose frontend image not required this session) | Playwright against localhost:3000 |
| External GEE | service account + project `ssri-504721` | **`GEE_INIT=OK`** (this session) |
| OpenTopography | `OPENTOPOGRAPHY_API_KEY` via dotenv helper | **`OPENTOPO_DEM=OK`** COP30 72×72 EPSG:4326 (this session) |
| Geophysical inputs | WGM2012 + EMAG2v3 under `data/geophysics/` | mounted `:ro` at `/data/geophysics` |

---

## 3. Repository State

| Item | Value |
|------|-------|
| Branch | `main` |
| HEAD | `29d8b1109671a755361db629c8699d764a96be7f` |
| HEAD message | `Allow worker healthcheck more time for cold Celery imports.` |

### Recent commits (most recent first)

1. `29d8b11` Allow worker healthcheck more time for cold Celery imports.
2. `21b2158` Fix worker health probe to import celery_app correctly.
3. `2074aad` Qualify SSRI against real runtime evidence and tighten production safety.
4. `49432b8` Fix worker healthcheck Compose variable interpolation.
5. `1237d56` Relax Celery worker healthcheck timeouts and align frontend CI with Next 16.

### Working tree (at report time)

- **Dirty / uncommitted:** yes (≈31 short-status entries when inspected).
- Gravity visualization work is **not fully committed**; key paths:

| Path | Git state | Role |
|------|-----------|------|
| `model/src/ssri_model/api/routes/layers.py` | untracked | Read-only Gravity GeoJSON API |
| `model/tests/test_layers_gravity.py` | untracked | Gravity endpoint tests |
| `model/src/ssri_model/api/app.py` | modified | Registers `layers` router |
| `frontend/app/dashboard/page.tsx` | modified | MapLibre Gravity layer + toggle |
| `frontend/lib/api.ts` | modified | `getGravityLayer()` client |
| `frontend/e2e/dashboard.spec.ts` | untracked | Playwright Gravity regression |
| `data/geophysics/**` | untracked | Raw/processed rasters + provenance JSON |
| `docs/production_qualification.md` | modified | This report |

Other uncommitted geophysics/qualification scripts and FeatureStack label updates remain in the tree from earlier qualification work.

---

## 4. Test Suite

### Complete model suite (fresh this session)

```text
Command: poetry run pytest -q --tb=line   (cwd: model/)
Result:  561 passed, 2 skipped, 1 warning in 399.04s
```

- Warning: thread exception in `test_concurrent_save_conflict` (`JobRecord.from_dict` / `attempt` None) — test still counted as passed by pytest; note for follow-up.
- **Did not invent older counts.** This is the live suite result from this qualification run.

### Gravity endpoint tests

```text
tests/test_layers_gravity.py → 2 passed
```

### Security / auth / production-gate subset (fresh)

```text
tests/test_layers_gravity.py
tests/test_production_gate.py
tests/test_security_baseline.py
tests/test_api_authentication.py
tests/test_api_auth_bypass.py
tests/test_api_rate_limiting.py
→ 33 passed in 57.78s
```

### Frontend

| Check | Result |
|-------|--------|
| `npx tsc --noEmit` | pass (exit 0) |
| `npm run build` | pass (Next.js 16.3.0; earlier this session) |
| Playwright `e2e/dashboard.spec.ts` | **6 passed** (42.0s) |

### Not run as a separate named “infrastructure-only” mega-suite

Infrastructure coverage is included inside the 561-test model suite (job store, rate limit, retry helpers, etc.). No additional external cloud CI run was performed.

---

## 5. Docker / Distributed Runtime

### Container status (end of evidence collection)

| Container | Status |
|-----------|--------|
| `ssri-api` | Up, **healthy** |
| `ssri-worker` | Up, **healthy** (was unhealthy earlier this session until worker image rebuild) |
| `ssri-postgres` | Up, **healthy** |
| `ssri-redis` | Up, **healthy** |
| `ssri-minio` | Up, **healthy** |

### Readiness

`GET /api/v1/ready` → HTTP 200:

```json
{
  "status": "ready",
  "service": "ssri-inference",
  "infrastructure": {
    "mode": "distributed",
    "ready": true,
    "components": [
      {"name": "configuration", "status": "ok"},
      {"name": "postgresql", "status": "ok", "detail": "connected"},
      {"name": "redis", "status": "ok", "detail": "connected"},
      {"name": "queue", "status": "ok", "detail": "reachable"}
    ]
  }
}
```

### Worker health incident (this session)

- Symptom: Compose marked worker **unhealthy**; probe output `celery app import failed (ImportError)`.
- Cause: **stale `ssri-worker` image** (API image had been rebuilt; worker service image had not).
- Remediation: `docker compose build worker` + recreate → import OK; status **healthy**.
- Functional note: even while unhealthy, earlier logs showed successful `ssri.execute_job` completions (health probe ≠ job execution).

### Geophysics mount

Compose mounts `../data/geophysics:/data/geophysics:ro` with defaults:

- `GRAVITY_DATA_PATH=/data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif`
- `MAGNETIC_DATA_PATH=/data/geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif`

Host `.env` has these paths **EMPTY**; containers rely on Compose defaults.

---

## 6. API Qualification

| Endpoint | Result |
|----------|--------|
| `GET /health` | `{"status":"ok","service":"ssri-inference"}` |
| `GET /api/v1/health` | same |
| `GET /api/v1/ready` | `ready` + distributed components ok |

### Operational assessment flow (`scripts/qualify_api_e2e.py`)

```text
E2E_API=OK
ready=200:ready
async_submit=202
async_final=completed
assess=200
assess_id=assess-99986fb6be4b4df7
spatial=True
bad_polygon=400
```

Interpretation:

- Async job create → worker execute → completed: **VERIFIED**
- Offline assess with spatial GeoTIFF artifact: **VERIFIED** (`spatial=True`)
- Invalid polygon rejection: **VERIFIED** (HTTP 400)

### Live point assess without offline fixtures

```text
POST /api/v1/assess  {point: Lagos, hazards, mc_samples}
→ HTTP 400  {"error":{"code":"INVALID_REQUEST","message":"Assessment requires 'checkpoint'."}}
```

Live acquisition also requires `SSRI_LIVE_ACQUISITION_ENABLED=true` (absent from `.env` → defaults **false**).

---

## 7. Gravity Qualification (mandatory)

### A. Model-input chain

```
WGM2012 raw .grd
  → processed GeoTIFF (Lagos clip)
  → load_gravity / FeatureStack align EPSG:32631 @ 30 m
  → channel "gravity" in CHANNEL_ORDER
```

| Field | Evidence |
|-------|----------|
| Dataset name | **WGM2012 Complete Spherical Bouguer anomaly** |
| Provider | Bureau Gravimétrique International (BGI) |
| DOI | https://doi.org/10.18168/bgi.23 |
| Raw file | `data/geophysics/raw/WGM2012_Bouguer_ponc_2min.grd` (present, ~233 MB) |
| Source note | Official BGI FTP hostname no longer resolves; obtained via Internet Archive snapshot of authoritative BGI distribution (provenance JSON) |
| Units | mGal |
| Native resolution | ~2 arc-minutes (regional) |
| Processed CRS | EPSG:4326 |
| Nodata | `-9999` |
| AOI (processed) | `(2.5, 5.5)–(4.5, 7.5)` WGS84 |
| Processed file | `data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif` |
| Standalone | **`GRAVITY_RASTER=OK`** (`qualify_geophysics_rasters.py`) |
| FeatureStack | **`FEATURESTACK_GEOPHYSICS=OK`** — `TARGET_CRS=EPSG:32631`, `TARGET_SHAPE=369x369`, `TARGET_RES_M=30.000`, `GRAVITY_VALID=136152`, `GRAVITY_PROVIDER=wgm2012_bouguer` |
| EIGEN-6C4 naming | **Not used**. Metadata/API title = WGM2012; provider label `wgm2012_bouguer` |

### B. Visualization chain

```
WGM2012 GeoTIFF
  → GET /api/v1/layers/gravity
  → GeoJSON FeatureCollection (EPSG:4326 lon/lat polygons)
  → MapLibre source ssri-gravity / layers ssri-gravity-fill + outline
  → dashboard toggle
```

| Check | Evidence |
|-------|----------|
| Live HTTP | **200** |
| Title/dataset | `WGM2012 Complete Spherical Bouguer anomaly` |
| Features (max_cells=500 sample) | 400 polygons; values finite mGal (e.g. min≈126.7 max≈290.6); nodata `-9999` |
| CRS for MapLibre | EPSG:4326 lon/lat (not UTM directly) |
| Frontend | Panel title WGM2012; `data-gravity-loaded=true` |
| Playwright | Gravity visibility toggle test **passed** |
| Backend FeatureStack mutation by viz fix | **None** (read-only raster→GeoJSON endpoint) |

### Scientific limitation (mandatory)

WGM2012 is approximately a **2′ regional gravity grid**. Resampling onto the **30 m** SSRI target grid **does not create 30 m-native geophysical information**. Display cells from `/layers/gravity` are further downsampled for map payload size.

---

## 8. Magnetic Qualification

```
EMAG2v3 UpCont GeoTIFF
  → processed Lagos clip
  → load_magnetics / FeatureStack align EPSG:32631 @ 30 m
  → channel "magnetics"
```

| Field | Evidence |
|-------|----------|
| Dataset | **EMAG2v3 4 km upward-continued total-field magnetic anomaly** |
| Provider | NOAA / NCEI |
| Version | `EMAG2_V3_20170530` |
| DOI | https://doi.org/10.7289/V5H70CVX |
| Raw | `data/geophysics/raw/EMAG2_V3_20170530_UpCont.tif` (~240 MB) |
| Units | nT |
| Native resolution | ~2 arc-minutes |
| Processed CRS | EPSG:4326 |
| Nodata | **`99999`** (preserved; not treated as valid anomaly) |
| Processed | `data/geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif` |
| Standalone | **`MAGNETIC_RASTER=OK`** |
| FeatureStack | `MAGNETIC_VALID=121023`, minmax ≈ 13.96–24.16 nT on test AOI align, provider `emag2v3_uc4km` |
| Docker mount | same `/data/geophysics:ro` |
| Frontend magnetics map layer | **NOT IMPLEMENTED** (no `ssri-magnetic` layer in dashboard) |

### Scientific limitation

Same as gravity: regional ~2′ product; 30 m alignment is resampled, not native resolution.

---

## 9. FeatureStack Qualification

### Channel contract (`CHANNEL_ORDER`, length **13**)

1. elevation  
2. slope  
3. plan_curvature  
4. profile_curvature  
5. twi  
6. relative_relief  
7. valley_depth  
8. ndvi  
9. ndwi  
10. clay_mineral_ratio  
11. iron_oxide_index  
12. gravity  
13. magnetics  

### Channel audit (`qualify_featurestack_channels.py`)

| Channel group | Status |
|---------------|--------|
| DEM-derived (7) | `CONFIG_PRESENT` |
| GEE spectral (4) | **`INIT_BLOCKED_IAM`** |
| gravity | `CONFIG_PRESENT` + loader/align **VERIFIED** |
| magnetics | `CONFIG_PRESENT` + loader/align **VERIFIED** |

```text
BLOCKED_CHANNELS=ndvi,ndwi,clay_mineral_ratio,iron_oxide_index
NOTE=zeros/nodata fill is not enabled for missing gravity/magnetics; pipeline raises GeophysicsConfigError instead.
GEE_RUNTIME=INIT_BLOCKED_IAM
```

### Geophysics align sample (verified)

| Metric | Value |
|--------|-------|
| CRS | EPSG:32631 |
| Shape | 369×369 |
| Resolution | 30 m |
| Gravity finite valid | 136152 |
| Magnetic finite valid | 121023 |

**Full live FeatureStack** (DEM download + GEE + geophysics together): **BLOCKED** by GEE init (and live flag / OpenTopo runtime verification gaps below).

---

## 10. GEE Qualification

```text
scripts/qualify_gee_init.py  (fresh this session)
CREDS_BASENAME=earth-engine.json
CREDS_HAS_PRIVATE_KEY=True
CREDS_TYPE=service_account
SA_MATCH=True
PROJECT_LEN=11
PROJECT_LOOKS_ID=True
GEE_INIT=FAIL type=GEEInitializationError
CAUSE_TYPE=EEException
CAUSE=Caller does not have required permission to use project ssri-504721.
      Grant roles/serviceusage.serviceUsageConsumer
      (or serviceusage.services.use)
```

### Status: **`GEE_INIT=BLOCKED`**

**External dependency:** GCP IAM on project **`ssri-504721`** — grant Earth Engine service account **`roles/serviceusage.serviceUsageConsumer`**.  
Credentials path/type look structurally valid; this is **not** a missing-key-file failure.

No credential files were modified.

---

## 11. Full Live Lagos Assessment

**Attempted path:** live Lagos AOI → GEE/OpenTopo → gravity → magnetics → FeatureStack → model → artifact → storage → API → UI.

| Gate | Result |
|------|--------|
| `SSRI_LIVE_ACQUISITION_ENABLED` | **ABSENT** in `.env` → defaults **false** |
| API live assess without checkpoint | HTTP **400** `Assessment requires 'checkpoint'` |
| GEE init | **BLOCKED** (IAM) |
| Offline assess substitute | Available and verified — **not** accepted as live success |

### First blocking dependency (ordered)

1. **GCP IAM** for Earth Engine (`serviceusage.serviceUsageConsumer` on `ssri-504721`) — blocks spectral FeatureStack.  
2. Enable **`SSRI_LIVE_ACQUISITION_ENABLED=true`** for API live acquisition path.  
3. Provide a valid **checkpoint** for `/assess` even on live AOI.  
4. Confirm OpenTopography download in the same process environment that serves the API.

**Verdict:** Full live Lagos assessment = **BLOCKED** (not successful).

---

## 12. Frontend Qualification

| Capability | Status | Evidence |
|------------|--------|----------|
| Dashboard loads | VERIFIED | Playwright + HTTP 200 |
| MapLibre init | VERIFIED | `ssri-map` visible; map-ready |
| Basemap | VERIFIED | Prefer demotiles; local `/map-style.json` fallback |
| Gravity layer | VERIFIED | WGM2012 title; loaded; visible; toggle |
| Magnetics layer | **NOT IMPLEMENTED** | No magnetic MapLibre layer code |
| Hazard layers on map | **NOT VERIFIED as map overlays** | Hazard selection is form UI; assess results are side-panel profiles |
| Point assessment validation | VERIFIED | Playwright |
| Polygon assessment validation | VERIFIED | Playwright |
| Loading/error states | VERIFIED | Gravity panel loading / unavailable text |
| API integration | VERIFIED | API status line + gravity fetch |
| Existing map functions after Gravity fix | VERIFIED | Prior 5 smoke tests still pass + Gravity = 6/6 |

### Playwright (fresh)

```text
6 passed (42.0s)
including: Gravity WGM2012 layer loads and visibility toggle works
```

---

## 13. Gravity API / Map Architecture Review

**File:** `model/src/ssri_model/api/routes/layers.py`

| Property | Assessment |
|----------|------------|
| Read-only | Yes — reads GeoTIFF; no writes |
| FeatureStack mutation | None |
| Dataset mutation | None |
| CRS | Requires / emits **EPSG:4326** lon/lat polygons for MapLibre |
| GeoJSON | FeatureCollection of Polygon cells with `value` (mGal) |
| Sampling | Downsamples when valid cells > `max_cells` |
| Provenance metadata | title/dataset/provider/units/resolution/crs/nodata/minmax/limitation |
| Nodata | Masked via nodata + non-finite |
| Request bounds | `max_cells` Query **ge=100, le=20000** (default 2500) |
| Payload size | Bounded by max_cells; still can be large at 20k polygons |
| Auth | **No auth dependency** on this route — publicly readable when API is reachable |
| Appropriateness | Acceptable while `AuthConfig.enabled=false` (current). **Risk:** if production auth is enabled later, this route remains open unless wrapped — report as security follow-up |

DoS note: CPU/memory cost of raster scan + GeoJSON serialization scales with `max_cells` and raster size; cap mitigates but does not eliminate load.

---

## 14. Security Qualification

| Topic | Evidence |
|-------|----------|
| Fail-closed production gate | Unit tests in `test_production_gate.py` (subset 33 passed) |
| Auth unit tests | `test_api_authentication.py`, `test_api_auth_bypass.py` — passed in subset |
| Rate limiting tests | `test_api_rate_limiting.py` — passed in subset |
| Security baseline | `test_security_baseline.py` — passed in subset |
| CORS | Gravity response includes `access-control-allow-origin: http://localhost:3000` |
| Invalid polygon | E2E `bad_polygon=400` |
| GeoJSON validation | Covered by API E2E + assess routes |
| Runtime auth enabled | `SSRI_AUTH_ENABLED` **ABSENT** → AuthConfig default `enabled=False`, `development_auth_mode=True` |
| Production auth bypass | Gate forbids disabled auth / development mode in production (code + tests) — **runtime production mode NOT exercised** |
| Layers endpoint auth | Unauthenticated (see §13) |
| Signed URLs | MinIO qualify returned `SIGNED_URL_SCHEME=http` |

**Auth overall:** **PARTIALLY VERIFIED** (strong unit coverage; live stack currently runs with auth disabled by default).

---

## 15. Object Storage Qualification

| Check | Result |
|-------|--------|
| MinIO container | healthy |
| Host qualify with `SSRI_OBJECT_STORAGE_ENDPOINT=http://127.0.0.1:9000` | **`MINIO_S3=OK`** (put → signed URL → download integrity → delete) |
| Host qualify with endpoint `http://minio:9000` | **FAIL** `EndpointConnectionError` (expected from host DNS) |
| Assess spatial artifact | E2E `spatial=True` |

---

## 16. Recovery / Reliability

| Check | Status | Evidence |
|-------|--------|----------|
| API restart → ready | **VERIFIED** | `docker restart ssri-api` (+ redis); `API_RECOVERY=OK after_attempts=4`; ready JSON ok |
| Redis restart coexistence | Exercised with API restart above; ready still reports redis connected |
| Worker restart / image recreate | **VERIFIED** | force-recreate + rebuild → healthy |
| PostgreSQL readiness | **VERIFIED** via ready endpoint |
| MinIO readiness | **VERIFIED** via docker health + storage qualify |
| Job completion after infra up | **VERIFIED** via E2E async job completed |
| Stale-job / heartbeat deep tests | Covered in unit suite; **not** separately re-demoed as chaos drill |

---

## 17. Performance

**NOT VERIFIED**

No dedicated latency benchmark script was found/run this session. No p50/p95/p99 numbers are reported. Local Docker timings must not be extrapolated to production capacity.

---

## 18. Scientific Validation

| Category | Status |
|----------|--------|
| Engineering validation | VERIFIED (tests, offline assess, geophysics load/align, Gravity UI) |
| Geophysical input validation | VERIFIED for WGM2012 + EMAG2v3 loaders/alignment |
| Model validation (labelled test metrics) | **NOT VERIFIED** |
| Calibration validation | **NOT VERIFIED** |
| Real-world hazard validation (subsidence / landslide / sinkhole) | **NOT VERIFIED** |

### SCIENTIFIC_VALIDATION=NOT VERIFIED

**Needed:** curated labelled validation AOIs/events for each hazard class, held-out evaluation protocol, and published metrics from that protocol. No AUC/ROC/precision/recall/F1 values are claimed here.

**Lagos InSAR (DOI `10.7294/19738957`) qualification (2026-09-08):** Classified **`BENCHMARK-ONLY`** — independent VLM / building-collapse risk reference for Lagos; **not** SSRI `label.tif` ground truth; **not** training-suitable without a separate approved protocol. Dataset deposit v1 states **CC0 1.0**; accompanying paper is **CC BY-NC 4.0**. See `docs/dataset_candidates_report.md` (Lagos InSAR qualification section).

**Still required for formal scientific validation:**

| Class | Public Lagos status | Still required |
|-------|---------------------|----------------|
| `subsidence` | BENCHMARK-ONLY InSAR VLM available | Prefer independent geological/engineering labels; optional VLM benchmark harness (separate approval) |
| `landslide` | `PUBLIC_LAGOS_DATA_NOT_FOUND` | Institutional landslide polygon/point inventory for Lagos / SW Nigeria |
| `sinkhole` | `PUBLIC_LAGOS_DATA_NOT_FOUND` | Institutional verified sinkhole/collapse inventory for Lagos / analogous Nigerian settings |

**A1 is not scientifically unblocked.**
---

## 19. Data Provenance

| Dataset | Provider | Product | Resolution | Units | CRS | License/Access | Current Status |
|---------|----------|---------|------------|-------|-----|----------------|----------------|
| WGM2012 | BGI | Complete Spherical Bouguer | ~2′ | mGal | EPSG:4326 (processed) | Academic/research per BGI disclaimer (provenance JSON) | **VERIFIED** ingest + viz |
| EMAG2v3 | NOAA/NCEI | UpCont 4 km (`EMAG2_V3_20170530`) | ~2′ | nT | EPSG:4326 (processed) | Official NOAA distribution (DOI recorded) | **VERIFIED** ingest; no map layer |
| OpenTopography / Copernicus DEM | OpenTopography | DEM download path in code | DEM-native / resampled to 30 m | m | AOI-dependent | Requires API key | Key **SET** in `.env`; download **NOT VERIFIED** this run |
| Sentinel-2 indices via GEE | Google Earth Engine | NDVI/NDWI/clay/iron | GEE export → 30 m target | index | target UTM | GCP project IAM required | **BLOCKED** IAM |
| Offline assess fixtures | Local | features `.npy` + checkpoint | n/a | n/a | n/a | Internal | **VERIFIED** via E2E |

Licensing wording for BGI/NOAA is taken from local provenance notes / DOI references — not independent legal review.

---

## 20. Known Limitations

### Blocking

1. **GEE IAM** — `roles/serviceusage.serviceUsageConsumer` missing on `ssri-504721` → no live spectral FeatureStack / full live Lagos assess.  
2. **Live acquisition disabled** — `SSRI_LIVE_ACQUISITION_ENABLED` unset.  
3. **Scientific validation data** — absent → cannot claim VALIDATION READY.  
4. **Cloud deployment** — not evidenced.

### Non-blocking

1. Gravity visualization work still **uncommitted** on `main`.  
2. Magnetics MapLibre layer not implemented.  
3. Hazard “layers” are not separate map overlays.  
4. `/layers/gravity` unauthenticated.  
5. Host MinIO qualify requires `127.0.0.1` not Docker DNS name `minio`.  
6. OpenTopography qualify script does not auto-load `.env` (false `missing_api_key` on bare `poetry run`).  
7. Pytest warning in concurrent job-store test thread.

### Scientific

1. WGM2012 / EMAG2v3 are regional ~2′; 30 m grid is resampled.  
2. Gravity map cells are further downsampled for UI.  
3. No labelled hazard performance metrics.

### Infrastructure

1. Worker health depends on keeping **worker image** rebuilt with API (separate Compose image name).  
2. Frontend this session used host `npm run dev`, not necessarily Compose `ssri-frontend` image.  
3. Auth disabled in current local `.env` posture.

### Data

1. Geophysics AOI clip is Lagos margin, not global.  
2. Raw geophysics files are large and untracked.  
3. GEE spectral channels unavailable until IAM fixed.

---

## 21. Qualification Matrix

| Capability | Status | Evidence | Blocking? |
|------------|--------|----------|-----------|
| Model tests | VERIFIED | 561 passed, 2 skipped | No |
| API | VERIFIED | health/ready + E2E assess | No |
| Auth | PARTIAL | unit/security subset pass; runtime auth disabled | No for demo; Yes for locked production |
| Docker | VERIFIED | five services up | No |
| PostgreSQL | VERIFIED | ready connected | No |
| Redis | VERIFIED | ready connected | No |
| Celery worker | VERIFIED | healthy + E2E job completed | No |
| MinIO | VERIFIED | health + MINIO_S3=OK | No |
| Gravity ingestion | VERIFIED | GRAVITY_RASTER + FEATURESTACK_GEOPHYSICS | No |
| Gravity API | VERIFIED | `/layers/gravity` 200 | No |
| Gravity map | VERIFIED | Playwright Gravity test | No |
| Magnetics ingestion | VERIFIED | MAGNETIC_RASTER + FeatureStack | No |
| FeatureStack (full live) | BLOCKED | GEE IAM; spectral blocked | **Yes** for live AOI |
| OpenTopography | PARTIAL | key SET; download NOT VERIFIED this run | Soft / next after GEE |
| GEE | BLOCKED | qualify_gee_init FAIL IAM | **Yes** |
| Full live Lagos assessment | BLOCKED | live flag + GEE + checkpoint | **Yes** |
| Frontend | VERIFIED | tsc/build/Playwright | No |
| Browser E2E | VERIFIED | 6/6 | No |
| Recovery | PARTIAL | API/redis restart OK; not full chaos suite | No |
| Scientific validation | NOT VERIFIED | no labelled metrics | **Yes** for VALIDATION READY |
| Cloud deployment | NOT VERIFIED | none | **Yes** for PRODUCTION READY |

---

## 22. Exact Remaining Blockers (ranked)

1. **Highest — GCP IAM for Earth Engine**  
   - Blocked: GEE init, spectral channels, full live FeatureStack.  
   - Action: Grant `roles/serviceusage.serviceUsageConsumer` to the EE service account on `ssri-504721`.  
   - Type: **external IAM** (not code).

2. **Next — Enable and prove live acquisition end-to-end**  
   - Blocked: API live AOI path (`SSRI_LIVE_ACQUISITION_ENABLED`), OpenTopo DEM in API environment, live assess with checkpoint.  
   - Action: Set live flag; confirm OpenTopo from API container; run one Lagos live assess with real checkpoint.  
   - Type: **configuration + operational verification**.

3. **Next — Scientific validation dataset + evaluation**  
   - Blocked: VALIDATION READY / any accuracy claims.  
   - Action: Assemble labelled hazard cases; run evaluator; publish metrics.  
   - Type: **scientific validation / data**.

4. **Then — Cloud deployment qualification**  
   - Blocked: PRODUCTION READY deployment claim.  
   - Action: Deploy to target cloud; re-run gates there.  
   - Type: **infrastructure**.

---

## 23. Recommended Next Step

**Obtain or train a non-fixture checkpoint** (real `dataset_manifest`, dropout > 0) from labelled SSRI hazard data, then re-run one Lagos live `/assess` with `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false`. Parallel scientific track: assemble labelled validation for `subsidence` / `landslide` / `sinkhole` (InSAR DOI `10.7294/19738957` stays **BENCHMARK-ONLY** unless a separate protocol is approved).

---

## 24. Final Verdict

```text
CURRENT QUALIFICATION VERDICT:
RESEARCH READY — LIVE PIPELINE VERIFIED

ENGINEERING: READY (offline + Gravity viz + distributed local Docker + live AOI path)
OPERATIONAL: PARTIALLY READY (stack healthy; live flags via controlled override; WBT baked in Dockerfile)
SCIENTIFIC: NOT READY (SCIENTIFIC_VALIDATION=NOT VERIFIED)
EXTERNAL SERVICES: VERIFIED this session (GEE_INIT=OK; OPENTOPO_DEM=OK; live FeatureStack)
DEPLOYMENT: NOT READY (local Docker only; no cloud evidence; fixture checkpoint only)
```

**Why this level:** Live multi-sensor Lagos assessment through the real API succeeded as an **engineering** demonstration. Hazard scores came from an **e2e fixture** checkpoint (zero-width CIs expected). No labelled validation metrics exist — do not treat scores as scientifically validated.

---

## 25. Checkpoint + live qualification evidence (2026-09-08, post-`c13cac7`)

### Repository checkpoint

| Item | Value |
|------|-------|
| Branch | `main` |
| Checkpoint commit | `c13cac766fd5ae5d5a7ab97e27f201f8da39ab7d` |
| Message | `Checkpoint qualified geophysics and scientific-data qualification` |
| Pre-checkpoint model tests | **574 passed**, 1 warning (`test_concurrent_save_conflict`) |
| Pre-checkpoint frontend | `tsc --noEmit` OK; `npm run build` OK |
| Pre-checkpoint Playwright | Failed in agent sandbox (Chromium missing) — not treated as product regression |

### GEE

```text
GEE_INIT=OK
```

- Service account: `ssri-earth-engine@ssri-504721.iam.gserviceaccount.com`
- Project: `ssri-504721`
- Credentials mounted at `/credentials/earth-engine.json` (not committed)

### OpenTopography (host qualify via dotenv helper)

```text
OPENTOPO_DEM=OK
DATASET=COP30
AOI_BBOX=(3.37, 6.51, 3.39, 6.53)
DEM_BYTES=25664
DEM_SHAPE=(72, 72)
CRS=EPSG:4326
RESOLUTION_XY≈(0.0002778°, 0.0002778°)
NODATA=-9999.0
```

Artifact was temporary (not committed).

### Live acquisition configuration

| Flag / component | State |
|------------------|-------|
| `SSRI_LIVE_ACQUISITION_ENABLED` | **true** on api + worker via Compose host-env recreate (repo/`.env.example` default remains **false**) |
| `SSRI_ALLOW_FIXTURE_CHECKPOINTS` | **true** for this controlled engineering run only |
| `SSRI_API_ENVIRONMENT` | `staging` |
| WhiteboxTools | First live attempt failed: `PermissionError` downloading WBT into non-writable site-packages. Remediated by root install in running containers + Dockerfile `download_wbt` at image build |

### Model checkpoint used

| Item | Value |
|------|-------|
| Path | `/data/outputs/e2e-job/checkpoint.pt` |
| sha256 | `ff30ff001dd14478e609819c85d2176638f57cce2f891364cb8ceb8b954621af` |
| Load | **OK** (`in_channels=13`, `num_classes=3`) |
| Identity | `dataset_manifest.name=e2e` / version `0` → **`is_fixture_checkpoint=true`** |
| Production-trained? | **No** |

### Real Lagos assessment (ONE run)

| Item | Value |
|------|-------|
| Endpoint | `POST /api/v1/assess` |
| Request | point `(lat=6.52, lon=3.38)`, `checkpoint` as above, `mc_samples=4`, `produce_geotiff=true` |
| HTTP | **200** |
| `assessment_id` | `assess-8d74bea1a7b697af` |
| Duration | ~27 s |
| Live acquisition | Yes — `feature_stack.npy/.tif` + `manifest.json` under assessment `acquisition/` |
| FeatureStack | shape `(13, 74, 74)`, CRS `EPSG:32631`, 30 m, `dem=COP30`, gravity `wgm2012_bouguer`, magnetics `emag2v3_uc4km`, spectral channels present |
| Spatial output | `subsidence_probability.tif` + object-storage URL recorded |
| Hazards returned | `subsidence`, `landslide`, `sinkhole` (scores are **fixture-model outputs**, not validated) |
| Uncertainty | Zero-width CIs (fixture / no informative dropout) |
| Domain similarity | `calibrated=false`, score `null`, tier Low |

### Scientific validation (unchanged)

```text
SCIENTIFIC_VALIDATION=NOT VERIFIED
```

Classes remain `subsidence`, `landslide`, `sinkhole`. Flood is not an SSRI training label. Lagos InSAR DOI `10.7294/19738957` remains **BENCHMARK-ONLY**.

---

## 26. Production-checkpoint readiness audit (2026-09-08)

### Hard gates

| Gate | Status |
|------|--------|
| Live GEE | **VERIFIED** (`GEE_INIT=OK`) |
| OpenTopography | **VERIFIED** (`OPENTOPO_DEM=OK`) |
| Live FeatureStack | **VERIFIED** (13ch, 30 m, EPSG:32631) |
| Training data | **BLOCKED** (no labelled SSRI dataset in-repo) |
| Dataset leakage audit | **BLOCKED** (no production dataset to audit) |
| Training | **NOT RUN** (blocked on data) |
| Production checkpoint | **BLOCKED** |
| Real Lagos inference with production checkpoint | **BLOCKED** (fixture-only weights exist) |
| Scientific labels | **MISSING** |
| Scientific validation | **NOT VERIFIED** |
| Domain calibration | **UNCALIBRATED** (`SSRI_DOMAIN_CENTROID_PATH` unset) |
| Production deployment | **NOT READY** |

### Training pipeline (code present — data absent)

| Capability | Location | Entry |
|------------|----------|-------|
| Dataset build | `ssri_model.dataset.DatasetBuilder` + `LocalRasterLabelProvider` | Python API |
| Dataset load | `ssri_model.ml.SSRIDataset` | Python API |
| Train | `ssri_model.training.Trainer` + `TrainingConfig` | Python API (see `STAGE_2_5_TRAINING.md`) |
| Evaluate | `ssri_model.evaluation.Evaluator` / `evaluate_checkpoint` | Python API (`STAGE_2_6_EVALUATION.md`) |
| Scientific audit | `ssri_model.scientific` | `poetry run python -m ssri_model.scientific audit\|labels\|features\|spatial\|report\|review …` |
| Inference batch | `ssri_model.orchestration` | `poetry run python -m ssri_model.orchestration run\|status\|resume …` |
| Inference single | `ssri_model.inference` | `poetry run python -m ssri_model.inference …` |

Class mapping (unchanged): **subsidence=0**, **landslide=1**, **sinkhole=2**; `LABEL_NODATA=-1`; 13 `CHANNEL_NAMES`.

### Pipeline caveats (fix when labels arrive — do not weaken gates)

Confirmed by training-pipeline audit ([Audit SSRI training pipeline](26a5646b-d061-4b3d-999d-a793dd09d57d)):

| Issue | Impact |
|-------|--------|
| `write_statistics` aggregates **train+val+test** | Normalization is not train-only; fix or document before claiming no stats leakage |
| `DatasetBuilder` split is ID-random, not spatial-blocked | Run Stage 2.9 `spatial` / leakage audits before train; do not skip |
| Default `SSRIModelConfig.dropout=0.0` | No `Dropout2d` → MC CIs stay zero-width unless trained with `dropout>0` |
| `PolygonLabelProvider` / `RemoteLabelProvider` | `NotImplementedError` — use `LocalRasterLabelProvider` only |
| No train/eval poetry CLI | Library API only (`Trainer`, `Evaluator`) |

Label-data audit ([Audit available label datasets](0eb4b729-16ae-4ba1-81db-0f71d0d16ac7)): **0** persistent `label.tif` on host or Docker `/data`; geophysics features only.

### e2e fixture (not production)

Path `/data/outputs/e2e-job/checkpoint.pt` remains **`is_fixture_checkpoint=true`** (`dataset_manifest.name=e2e`). Must not be relabelled production.

### Runtime safety (post-audit)

- `.env.example`: `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false`, `SSRI_LIVE_ACQUISITION_ENABLED=false`
- Staging containers after restore: `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false` (api+worker); live acquisition may remain enabled for research (`true`) without fixture bypass
- Engineering readiness subset (training/eval/scientific/checkpoint/uncertainty/security): **216 passed**

### Verdict addition

```text
RESEARCH READY — LIVE PIPELINE VERIFIED
PRODUCTION_CHECKPOINT=BLOCKED
TRAINING_BLOCKED
SCIENTIFIC_VALIDATION=NOT VERIFIED
```

See `docs/dataset_candidates_report.md` (Production training readiness) and `PROGRESS.md`.

---

## 27. Clean Docker rebuild + concurrency + live fixture regression (2026-09-08)

### Clean image qualification (no manual WBT install)

| Check | Result |
|-------|--------|
| `docker compose build --no-cache api` | **OK** — runtime step downloaded WBT into site-packages |
| `docker compose build --no-cache worker` | **OK** — same Dockerfile |
| API `whitebox_tools` present as `app` user | **True** (~20 848 880 bytes) |
| Worker `whitebox_tools` present | **True** |
| `/api/v1/ready` | ready (postgres+redis+queue) |
| Manual `download_wbt` in running container | **Not used** |

### Concurrent job-store test

| Finding | Detail |
|---------|--------|
| Root cause | Flake from **SQLite StaticPool `:memory:` shared across threads** (undefined), not a Postgres production OCC bug in `claim`/`transition` |
| `save()` semantics | Reload-then-update upsert; classic caller-version OCC is on `transition`/`claim` |
| Fix | File-backed store helper + deterministic upsert test; concurrent test no longer uses StaticPool memory DB |
| Stability | **8/8** runs of upsert+concurrent tests passed |
| Full suite | **575 passed** (0 failed, 0 warnings reported in summary) |

### Live Lagos on clean image

| Step | Result |
|------|--------|
| Fail-closed (`ALLOW_FIXTURE=false`, staging) | HTTP **400** fixture refused |
| Controlled allow + live assess | HTTP **200** `assess-886d57800cebbaf8` |
| Classification | **LIVE PIPELINE VERIFIED USING FIXTURE CHECKPOINT** (`e2e`, sha256 `ff30ff00…`) |
| FeatureStack | COP30 + WGM2012 + EMAG2v3; shape `[13,74,74]`; EPSG:32631; 30 m |
| Domain | uncalibrated |
| After run | restored `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false` |

### Checkpoint classification (unchanged)

```text
TRAINING_DATA_NOT_AVAILABLE
PRODUCTION_CHECKPOINT=BLOCKED
SCIENTIFIC_VALIDATION=NOT VERIFIED
```

---

## 28. Earth Engine sampleRectangle tiling + dashboard UX (2026-09-08)

### Root cause

Live FeatureStack acquisition called Earth Engine `Image.sampleRectangle` on the **entire** AOI via `clipToBoundsAndScale`. EE enforces a hard limit of **262,144 pixels per sample**. Larger Lagos AOIs (example failure: **314,070** pixels) raised:

`Image.sampleRectangle: Too many pixels in sample; must be <= 262144.`

### Fix (deterministic UTM tiling)

In `model/src/ssri_model/data/feature_engineering.py`:

- Plan non-overlapping tiles on the SSRI target UTM grid (`_ee_sample_tile_plan`), max tile side derived from a **250,000**-pixel safe budget (≤ EE 262,144).
- Sample each tile’s WGS84 bbox separately; align with existing SSRI grid logic; mosaic into the full FeatureStack.
- Does **not** lower resolution, crop the AOI, drop channels, or disable live acquisition.
- AOIs above `EE_SAMPLE_MAX_TOTAL_PIXELS` (20M) get a clear `FeatureStackError` instead of silent degradation.
- Sub-pixel WGM2012/EMAG2v3 window expand (`_window_covering_at_least_one_pixel` in `geophysics.py`) unchanged.

Tests: `model/tests/test_ee_sample_tiling.py` (below/at/above limit, Lagos-scale plan, recombination, channel count).

### Dashboard: coordinate entry + result modal

- **Method A:** existing map click / polygon draw.
- **Method B:** “Enter coordinates” (lat/lon + Locate) with validation (−90…90 / −180…180 / numeric); soft coverage hint for Lagos geophysics clip (~2.5–4.5°E, 5.5–7.5°N). Feeds the same `/api/v1/assess` path.
- After assess start: **AssessResultModal** opens (loading → success/error). Fixture checkpoints show **Research / fixture model**. Result retained; reopen from sidebar; View on map closes modal without leaving `/dashboard`.

### Status

Staging large Lagos AOI `(3.30–3.45°E, 6.45–6.60°N)` (~305k target pixels, 4 EE tiles):

- `/api/v1/assess` HTTP **200** `assess-76b3187de114b6b0`
- No `Too many pixels … 262144` failure
- Fixture checkpoint `e2e` (`is_fixture_checkpoint=true`) — **LIVE PIPELINE VERIFIED USING FIXTURE CHECKPOINT** only
- Fail-closed `SSRI_ALLOW_FIXTURE_CHECKPOINTS=false` restored after the run

```text
RESEARCH READY — LIVE PIPELINE VERIFIED
SCIENTIFIC_VALIDATION=NOT VERIFIED
```
