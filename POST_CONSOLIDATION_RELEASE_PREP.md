# SSRI — Post-Consolidation Release Preparation

**Date:** 2026-11-19  
**Reconciled tip (local `main` = `origin/main` before this report commit):** `0c4292901f731665c2eb3f3cdeac35d067353880`  
**Prior consolidation tip:** `55c98b901e077e73b98c6a2897efefd3c167fefa`  
**Actions performed:** git audit; Docker Postgres+Redis; integration tests; cancel settle re-runs; deployment audit.  
**Not performed this document commit:** deploy, branch deletion, production config changes.

Scientific validation remains **NOT_VALIDATED**. SYNTHETIC rehearsal ≠ geological truth. Abeokuta CRS/units remain unconfirmed.

---

## Confirmation gates (re-checked)

| # | Gate | Status |
|---|------|--------|
| 1 | Local `main` reconciled with `origin/main` | **YES** — both at merge tip `0c42929` (*Merge origin/main; content already contained via rewritten history*). Consolidation + frontend-align ancestry retained. Backups: `backup/local-main-55c98b9`, `backup/origin-main-21535e6`. |
| 2 | Cancellation flake + integration settled | **YES** — see §2 settle re-run (integration 2/2; job unit 22/22; cancel ×3 all pass) |
| 3 | This release-preparation report accounted for | **YES** — committed onto `main` with settle evidence |

---

## 1. Pre-push verification report

### Current reconciled state

| Check | Result |
|-------|--------|
| Local `main` / `origin/main` | Identical at `0c42929` after merge of remote PR #2 lineage into local consolidation (**ahead 0 / behind 0** before this report commit) |
| Working tree at reconcile check | Clean except this report + settle evidence (then committed) |
| Backup tag `backup/main-pre-consolidation-e89fa03` | Still `e89fa03` **OK** |
| Consolidation content on tip | `CONSOLIDATION_RELEASE_REPORT.md`, `ALIGNMENT_TABLE.md`, RC2 + frontend-align ancestors present |

### Historical divergence (resolved)

Earlier fetch had moved `origin/main` to `21535e6` (PR #2) while local sat at `55c98b9` (**ahead 46 / behind 21**). That divergence was reconciled by merge commit `0c42929` (duplicate rewritten history; product content kept).

### Fast-forward push safety

**At reconcile tip `0c42929`:** local and remote already matched — no push required for the merge itself.  
**After committing this report:** local will be ahead by documentation/evidence commits; a normal non-force `git push` is the expected next step **only with explicit authorization**.

---

## 2. Distributed integration test report

### Environment prepared

| Component | Action | Result |
|-----------|--------|--------|
| Docker Desktop | Started (was down) | Engine ready |
| `docker compose -f model/docker-compose.yml up -d` | Postgres 16 + Redis 7 | **healthy** on `:5432` / `:6379` |
| Schema | `init_schema()` → table `ssri_jobs` | Required before readiness |

Env used:

```text
SSRI_INTEGRATION_TESTS=1
SSRI_DATABASE_URL=postgresql+psycopg://ssri:ssri@localhost:5432/ssri
SSRI_REDIS_URL=redis://localhost:6379/0
```

### Official integration file (`tests/test_infrastructure_integration.py`)

| Run | `test_readiness_with_real_services` | `test_postgres_job_lifecycle` |
|-----|--------------------------------------|-------------------------------|
| First (empty DB, no prior migrate) | **FAILED** — `postgresql=unavailable`, detail `schema_missing`, `ready=False` | **PASSED** (fixture calls `init_schema`) |
| After explicit `init_schema` | **PASSED** | **PASSED** |

**Final distributed integration result (settle re-run on reconciled tip): 2 passed, 0 skipped, 0 failed**  
Evidence: `poc/release_shell/outputs/settle_integration.txt` (also earlier `post_consolidation_integration_after_migrate.txt`)

What this proves:

- Redis connectivity + queue enqueue/dequeue/ack
- Postgres durable job save → claim → COMPLETED lifecycle
- Distributed readiness **after** schema exists

What this does **not** prove:

- Full Celery worker consuming `ssri.execute_job` end-to-end in Compose `api`+`worker` containers
- Persistent dataset/checkpoint object storage across container restarts (volume lifecycle not exercised)
- Lease recovery sweeper against live Redis+Postgres (unit coverage only — see below)

### Related job behaviour (local/unit)

| Suite | Result | Notes |
|-------|--------|-------|
| Initial session | **21 passed, 1 failed** | `test_cancel_queued_job` once saw `running` instead of `cancelled` |
| Settle re-run (full job unit file set) | **22 passed, 0 failed** | `test_api_async_jobs` + recovery + retry together |
| Cancel isolated ×3 after settle | **3/3 PASSED** | `CANCEL_FAILS=0` |
| Verdict | **Settled for release gate** | Prior flake treated as race under load; current tip green on suite + repeats. Still not a live Celery cancel proof. |

### Storage note

Job table name is **`ssri_jobs`** (not `jobs`). Datasets/checkpoints for release-shell live under `{SSRI_API_OUTPUT_ROOT}/…` on the API host volume — Compose maps `ssri_data:/data`. Distributed integration tests did not upload a training zip through the worker path.

---

## 3. Production hosting requirements

### Service topology (from `infra/docker-compose.yml` + `.env.example` + `docs/operations.md`)

| Service | Role | Dependency |
|---------|------|------------|
| **Frontend** (Next.js) | Marketing + `/dashboard` + `/shell` + `/workspace` | Build-time `NEXT_PUBLIC_*`; HTTPS domain; API origin reachable; CORS allowlist on API |
| **FastAPI** (`ssri_model.api`) | `/api/v1/*` assess, jobs, training, release-shell | Postgres + Redis in `distributed` mode; output volume; auth key store; optional GEE/OpenTopo |
| **Worker** (Celery) | `ssri.execute_job` | Same DB/Redis/broker as API; shared `/data` outputs; CPU torch image |
| **PostgreSQL 16** | Durable jobs (`ssri_jobs`) | Must run `init_schema` / create_all before ready |
| **Redis 7** | Queue + optional idempotency | Broker + result backend |
| **Recovery** (optional profile) | Stale lease sweeper | `SSRI_LEASE_RECOVERY_ENABLED=true` — **must be scheduled**; code alone is not enough |
| **Object storage** | Assess GeoTIFF / artifacts | `local` volume or S3/MinIO/R2 |
| **Credentials volume** | GEE service account JSON | Mount `credentials/` read-only; never bake into image |

Historical frontend host noted in docs: `https://ssri-gamma.vercel.app`. Historical API host noted: Render (`ssri-api.onrender.com`). Treat as **UNKNOWN until reconfirmed**.

### Environment variables (names only — no secret values)

**Frontend (build-time):**

| Variable | Purpose |
|----------|---------|
| `NEXT_PUBLIC_API_URL` | API origin |
| `NEXT_PUBLIC_SSRI_API_KEY` | Authenticated assess/job calls when auth on |
| `NEXT_PUBLIC_SUPABASE_URL` / `NEXT_PUBLIC_SUPABASE_ANON_KEY` | Browser auth (never service role) |
| `NEXT_PUBLIC_MAP_STYLE_URL` | Optional map style |

**API / worker (runtime):**

| Variable | Production guidance |
|----------|---------------------|
| `SSRI_API_ENVIRONMENT` | `staging` / `production` |
| `SSRI_EXECUTION_MODE` | `distributed` |
| `SSRI_DATABASE_URL` | Postgres URL (`postgresql+psycopg://…`) |
| `SSRI_REDIS_URL` / `SSRI_CELERY_BROKER_URL` / `SSRI_CELERY_RESULT_BACKEND` | Redis |
| `SSRI_API_OUTPUT_ROOT` | Persistent volume path |
| `SSRI_AUTH_ENABLED` | **true** in production |
| `SSRI_AUTH_REQUIRE_IN_PRODUCTION` | true |
| `SSRI_AUTH_KEY_STORE` | Persistent keys JSON path |
| `SSRI_RATE_LIMIT_ENABLED` | true in production |
| `SSRI_CORS_ORIGINS` / `CORS_ORIGINS` | Exact frontend HTTPS origins — **no `*`** |
| `SSRI_RELEASE_SHELL` | Default **OFF**; enable only on intended shell staging |
| `SSRI_ASSESS_SOFTMAX` | Leave OFF unless rehearsal profile |
| `SSRI_DEMO_MODE` | **false** |
| `SSRI_LIVE_ACQUISITION_ENABLED` | true only with GEE/OpenTopo configured |
| `SSRI_ALLOW_FIXTURE_CHECKPOINTS` | **false** |
| `SSRI_TRUST_CLIENT_SCIENTIFIC_STATUS` | **false** in production |
| `SSRI_OBJECT_STORAGE_*` | Backend + bucket/endpoint/keys as needed |
| `GEE_PRIVATE_KEY_PATH` / `GOOGLE_APPLICATION_CREDENTIALS` / `GCP_PROJECT_ID` | Live AOI |
| `OPENTOPOGRAPHY_API_KEY` | DEM fallback |
| `SSRI_LEASE_RECOVERY_ENABLED` + interval/batch | On recovery service |
| `SSRI_JOB_LEASE_SECONDS` / `SSRI_MAX_ATTEMPTS` / heartbeats | Timeouts / retries |
| `SSRI_CELERY_CONCURRENCY` | Worker parallelism (CPU-bound; start at 1) |
| Supabase server: `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY` | Platform v4 — service role **server only** |

**Release-shell knobs (staging shell only):**  
`SSRI_RELEASE_SHELL_MIN_TILES`, `_MIN_BLOCKS`, `_MIN_HELD_OUT`, `_BUFFER_KM`, `_BLOCK_SIZE_DEG`/`_KM`, `SSRI_PREVIEW_UNEVALUATED_SCORES`.

### Resource / timeout expectations

- Assess SYNTHETIC CPU rehearsal measured **~14 s** (target 10 s) — size worker CPU and `mc_samples` accordingly.
- Job lease default 300 s; long training must heartbeat / not block HTTP.
- Upload caps already enforced (413 path) — preserve reverse-proxy body size limits ≥ API cap.
- Domain + HTTPS: terminate TLS at host (Vercel/Render/nginx); set CORS to that exact origin.

### Deploy checklist (no secrets)

1. Provision Postgres + Redis; create durable volumes.
2. Run schema init (`ssri_jobs`) before marking ready.
3. Deploy API + worker with shared output volume and identical broker/DB URLs.
4. Enable auth + rate limits; install API keys out-of-band.
5. Set CORS to frontend HTTPS origin(s).
6. Build frontend with staging/prod `NEXT_PUBLIC_*`.
7. Optionally enable release-shell **only** on staging shell service.
8. Mount GEE credentials if live AOI required; else keep live acquisition OFF.
9. Start recovery profile/sweeper for distributed leases.
10. Smoke: `/health`, `/api/v1/ready`, async job round-trip, then `smoke_staging.py` against staging URL.
11. Keep `SSRI_DEMO_MODE=false`; never present demo/SYNTHETIC as validated science.

---

## 4. Outstanding blockers

| Blocker | Impact | Action |
|---------|--------|--------|
| ~~Diverged `origin/main` vs local consolidation~~ | **Resolved** at `0c42929` | Report/evidence commit may leave local ahead — push only with authorization |
| Staging URL / API key / Supabase / GEE | Blocks hosted smoke & client live demo on real infra | Owner supplies; run `smoke_staging.py` |
| Schema must be initialized before ready | Fresh Postgres fails readiness (`schema_missing`) | Automate migrate/init in deploy |
| Cancel-job flake under suite load | Weakens confidence in cancellation race | Fix or harden `test_cancel_queued_job`; re-run full async suite |
| Full Compose api+worker e2e | Distributed path beyond queue/DB unit not re-run this session | `infra/docker-compose` e2e after reconcile |
| Abeokuta CRS/units/provenance | Client dataset not acceptance-ready as “validated data” | Complete `handoff/CLIENT_QUESTIONS.md` |
| Scientific validation | Cannot claim production geology | Keep NOT_VALIDATED; slope gates |

---

## 5. Client acceptance test report

### Scope honesty

This report separates **platform workflow readiness** from **scientific acceptance**. No result below is geological validation.

### Evidence used

| Source | Status |
|--------|--------|
| Committed Playwright SYNTHETIC rehearsal on consolidated lineage (`poc/release_shell/outputs/frontend_rehearsal/`) | **VERIFIED previously** — owner flow + assess error contracts both `ok: true` |
| Backend upload/CRS/geography/contract suites on consolidation tip | **VERIFIED** in consolidation (747/2, curated 180) |
| Live re-run of Playwright rehearsal in *this* session | **NOT RE-RUN** (3.5m; requires flag-ON API + UI servers) |
| Abeokuta client CSV as validated input | **NOT ACCEPTED** — CRS/units ASSUMED-FOR-TEST |

### Workflow matrix (client-facing)

| Step | Platform status | Notes |
|------|-----------------|-------|
| 1. Upload dataset | **PASS** (SYNTHETIC) | Shell zip upload + validate; contract tests cover failure modes |
| 2. Inspect structure | **PASS** | Validator + UI owner inputs |
| 3. CRS validation | **PASS WITH WARNINGS** | Explicit CRS required; geography route; placeholders mention EPSG examples but code does **not** silently assume 32631 |
| 4. Units / nodata | **PASS WITH WARNINGS** | Negative overburden WARN; Abeokuta units unconfirmed |
| 5. Layer / channel mapping | **PASS** | Schema v1/v2 from backend registry; UI derives hazards (3) not invented liquefaction |
| 6. Label inventory | **PASS** | Inventory endpoints + no-labels refusal |
| 7. Training (3-seed) | **PASS** (SYNTHETIC) | Rehearsal timings ~63 s wait for eval on CPU |
| 8. Evaluation | **PASS** | Gates may withhold (“no demonstrated skill beyond slope”) |
| 9. Checkpoint selection | **PASS** | Every seed embeds release-shell meta (CRS) — fixed in RC3 |
| 10. Inference / assess | **PASS WITH WARNINGS** | In-region assess ~14 s; out-of-region withholds; schema mismatch 400 plain language |
| 11. Spatial / report outputs | **PASS** | HTML report download; NOT_VALIDATED framing; wording guard |

### Incomplete / broken / caution UI flows

| Item | Severity | Detail |
|------|----------|--------|
| Assess latency ~14 s | Open | Exceeds informal 10 s demo target on SYNTHETIC CPU |
| Flag-OFF `/shell` | Expected | Shell routes refuse when `SSRI_RELEASE_SHELL` unset — demo must enable flag deliberately |
| Live map AOI without GEE | Incomplete for “live Earth” demos | Offline features / trained checkpoint path works; live acquisition needs credentials |
| Auth/Supabase missing locally | Incomplete for account flows | `/workspace` login depends on configured Supabase; shell owner path can run with API key / auth-off in dev only |
| Cancel under concurrency | Caution | One suite failure then two isolated passes — treat as flake until hardened |
| Client Abeokuta data | Blocked for “validated” narrative | Do not present as CRS-confirmed or scientifically validated |

### Client demo script (safe)

1. SYNTHETIC v2 template only for happy path.
2. Show CRS entry + validation FAIL/WARN honestly.
3. Train → evaluate → promote → dashboard 6 dp → report.
4. Show out-of-region withhold + schema-mismatch error.
5. State verbally: **NOT_VALIDATED**, research-ready platform, not insurance/engineering truth.

---

## Summary verdict

| Deliverable | Verdict |
|-------------|---------|
| Pre-push | Local tip correct & clean; **FF push unsafe** — remote moved to `21535e6` |
| Distributed integration | **PASS after schema init** (2/2); first run documented readiness failure without migrate |
| Production hosting | Checklist above; secrets not included |
| Client acceptance | SYNTHETIC platform workflow **ready to demonstrate**; scientific / Abeokuta acceptance **not ready** |
