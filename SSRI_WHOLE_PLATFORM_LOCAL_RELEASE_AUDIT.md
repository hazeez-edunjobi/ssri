# SSRI — Whole-Platform Local Release Audit

**Date:** 2026-11-24  
**Mode:** Read-only inspection (no code fixes, no Git write, no retrain, no deploy)  
**Baseline commit:** `44558779ffe93a0f2a3d151e8f0a9d309f7e8753`  
**Prior Abeokuta evidence:** preserved (`SSRI_FINAL_LOCAL_ABEOKUTA_COMPLETION_REPORT.md`, related `poc/` artifacts)

---

## 1. Executive summary

SSRI’s **authoritative local stack** (`model/` FastAPI + Celery worker, `frontend/` Next.js, Postgres/Redis, geological catalogue, Stage 2.5 assess) is operationally coherent for **local release**. Core advertised workflows—health/ready, live AOI assess, geological catalogue (including Abeokuta TMI), training/registry promote, platform account shell—are implemented and supported by recent acceptance evidence.

No **P0** security or data-integrity failures were proven in this audit. Remaining issues are **P2/P3** product/ops gaps (marketing API fiction, dual training surfaces, CORS vs unused DELETE, ungated operator pages, missing dedicated assess-history UI, lease recovery off by default) plus **scientific** limitations already documented (`NOT_VALIDATED`, synthetic checkpoint, unavailable Abeokuta lineament/overburden metres).

**Final decision: READY FOR LOCAL RELEASE**  
(with documented scientific limitations and a non-blocking remediation backlog)

---

## 2. Git and environment baseline

### Git

| Check | Result |
|---|---|
| Branch | `main` |
| HEAD | `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` |
| Message | Add honest catalogue overlays for lineament and overburden assess context. |
| Tracking | `main...origin/main [ahead 1]` |
| `git diff` / staged | Empty (no dirty tracked files) |
| Untracked (evidence only) | `SSRI_FINAL_LOCAL_ABEOKUTA_COMPLETION_REPORT.md`, `poc/abeokuta_final_local_completion_assess.json`, `poc/abeokuta_final_summary.txt`, plus this audit file when written |

`git log` (recent): `4455877` → `d8ac1bc` (pre-geological checkpoint) → `d6e877a` …

### Local services (live probe, no secrets)

| Probe | Result |
|---|---|
| `GET /api/v1/health` | ok |
| `GET /api/v1/ready` | ready — configuration/postgresql/redis/queue **ok**; `demo_mode=false`; active model `ssri-model-e7af3afcd0`; registry **NOT_VALIDATED** |
| Frontend `:3000` | HTTP 200 |
| Compose | `ssri-postgres` / `ssri-redis` healthy (session context) |

---

## 3. Repository architecture map

| Tree | Role | Authority |
|---|---|---|
| `model/src/ssri_model/` | FastAPI, inference, training, geological, jobs, Celery worker | **Authoritative** |
| `frontend/` | Next.js product + marketing | **Authoritative UI** |
| `infra/` | Docker Compose (api/worker/postgres/redis/frontend) | **Authoritative ops layout** |
| `supabase/migrations/` | Platform v4 schema / RLS | **Authoritative accounts DB** |
| `docs/`, root `SSRI_*.md` | Operations + historical reports | Evidence / narrative |
| `api/`, `worker/` | Stage-0 scaffolds | **Deprecated — do not extend** |
| `poc/` | Acceptance / assess evidence | Local artifacts |
| `data/outputs/` | Geological datasets, training registry, assessments | Runtime data (not Git product code) |

**Dual model stacks (do not mix):** Stage 2.5 `SSRIModel` (13-ch assess) vs foundation multitask (research CLI only). Liquefaction marketing ≠ live sinkhole class.

---

## 4. Backend / API findings

**Entry:** `model/src/ssri_model/api/app.py` · prefix `/api/v1`  
**Auth default (dev):** `SSRI_AUTH_ENABLED=false` → development principal (operator-equivalent) when development mode on.

### Capability matrix (summary)

| Capability | Route(s) | Implementation | Auth | FE uses? | Status |
|---|---|---|---|---|---|
| Health | `GET /health`, `/api/v1/health` | `routes/health.py` | none | yes (dashboard) | Complete |
| Ready | `GET /api/v1/ready` | `health.py` | none | yes | Complete |
| Sync assess | `POST /api/v1/assess` | `routes/assess.py` `assess_endpoint` | `RUN_ASSESS` | **yes** `/dashboard` | Complete (sync, heavy) |
| Async assess | — | **Not a separate job type** | — | no | Assess is sync-only by design |
| Inference sync/async | `/api/v1/inference`, `/async`, `/{id}` | `inference.py` | RUN_INFERENCE / READ_METADATA | operator/shell, not primary dashboard | Complete |
| Batch | `/api/v1/batch` (+ async/status) | `batch.py` | RUN_BATCH | no dedicated FE page | Complete API |
| Jobs get/cancel | `/api/v1/jobs/{id}` | `jobs.py` | READ_STATUS / RUN_INFERENCE | training/shell poll | Complete |
| Assessment history API | dedicated list | **Absent** | — | session “last result” only | Gap (P2) |
| Geological CRUD/process | `/api/v1/geological/*` | `geological.py` | MANAGE_GEOLOGICAL / READ_STATUS | `/geological` | Complete |
| Training Stage 2.5 | `/api/v1/training/*` | `training.py` | RUN_INFERENCE / READ_STATUS | `/training/operator` | Complete |
| Platform v4 | `/api/v1/platform/*` | `platform.py` | Supabase JWT | workspace/datasets/training/models | Complete (needs Supabase) |
| Auth keys | `/api/v1/auth/keys` | `auth_keys.py` | MANAGE_AUTH | no UI | Complete API |
| Demo scenarios | `/api/v1/demo/scenarios` | `demo.py` | none | gated presentation UI | Complete; 404 if demo off |
| Gravity layer | `/api/v1/layers/gravity` | `layers.py` | none | dashboard | Complete |
| Release shell | `/api/v1/release-shell/*` | `release_shell/routes.py` | mixed; flag-gated | `/shell` | Complete when `SSRI_RELEASE_SHELL` |

**Jobs:** `JobType` = `inference` | `batch` | `training` via `ssri.execute_job` (`model/.../worker/tasks.py`). Distributed mode needs Postgres job store + Redis + Celery (current local ready payload confirms queue reachable).

**Incomplete / stubs:** Deprecated root `api/` and `worker/` are health-only / empty Celery—not live. No evidence of placeholder handlers on mounted product routes.

**Contract note:** CORS allows `GET, POST, OPTIONS` only (`app.py`). Platform exposes `DELETE /platform/datasets/{id}` but frontend does not call DELETE—latent browser incompatibility if UI adds delete without CORS update (**F-02**).

---

## 5. ML and assessment lifecycle findings

Verified against code + prior Abeokuta completion evidence (not re-run here):

| Step | Status |
|---|---|
| AOI validation (point/polygon) | Implemented in assess path |
| Feature acquisition (live / `.npy`) | Live AOI when `SSRI_LIVE_ACQUISITION_ENABLED` |
| Preprocessing / channel contract | Enforces checkpoint `in_channels` vs tensor (13 vs 16 mismatch rejected) |
| Active checkpoint | Registry `active.json` → `ssri-model-e7af3afcd0` |
| Inference + MC uncertainty | `run_mc_dropout` / `assess_from_mc_samples` |
| Hazard scores | subsidence / landslide / sinkhole |
| Confidence / domain similarity | Present; often uncalibrated locally |
| Explanations / drivers | Attribution top features |
| Persistence | `_persist_assessment_response` under `{output_root}/assessments/` |
| Async assess | Not queued; sync HTTP |
| Conditioning overlays | Catalogue analytics; `used_in_inference=false` on live 13-ch |

**Checkpoint / architecture:** Unchanged 13-channel Stage 2.5. Synthetic rehearsal provenance must not be sold as real-world training. Scientific status **NOT_VALIDATED**.

**Known software/science boundary:** Degenerate credible intervals (identical bounds) are an uncertainty-reporting limitation, not proof of calibrated uncertainty.

---

## 6. Geological data findings

| Area | Status |
|---|---|
| CSV / ZIP-CSV ingest | Implemented + path-traversal rejection |
| CRS declare / transform / display bbox | Implemented (Abeokuta 32632→32631→4326) |
| Measurement types | TMI, overburden_thickness, lineament vectors, etc. |
| Catalogue list/detail/activation | Implemented |
| Magnetic processing products | Implemented |
| Coverage / AOI intersection | `/geological/coverage` |
| Conditioning overlays on assess | Committed in `4455877` |
| Downloads | original + derived |

**Abeokuta (`geo_be00a34ad6f4`):** Remains TMI (`z_meaning=total_magnetic_intensity`); Z is **not** overburden. Lineament/overburden unavailable for AOI without activated covering datasets—honest reporting verified in prior completion report. **Not reopened** in this audit; no regression suspected.

---

## 7. Frontend route-by-route findings

| Route | Renders / purpose | API | Gate | Notes |
|---|---|---|---|---|
| `/` `/about` `/hazards` `/platform` `/developers` | Marketing | none | public | `/developers` & `/platform` cite **unimplemented** `/v1/hazard` / SDK fiction (**F-01**) |
| `/login` `/signup` `/forgot-password` `/reset-password` `/verify-email` | Auth UX | Supabase | public | Google OAuth commented future |
| `/workspace` | Account home | platform | PlatformShell | OK |
| `/dashboard` | Live assess map | `POST /assess`, ready, gravity, geological context | **RequireSession** | Primary assess UI; last-result in-session |
| `/geological` `/geological/[id]` | Catalogue + TMI ops | geologicalApi | PlatformShell | Core geological UX |
| `/datasets` `/datasets/[id]` | Platform datasets | platformApi | PlatformShell | Stage 2.5 zip versions |
| `/training` `/training/[id]` | Platform training runs | platformApi | PlatformShell | Product trainer |
| `/training/operator` | Stage 2.5 operator | `/api/v1/training/*` | **No UI session gate** | Relies on API (**F-03**) |
| `/models` `/models/[id]` | Promote models | platformApi | PlatformShell | Promote needs registry id |
| `/activity` | Activity feed | platformApi | PlatformShell | Not full assess history |
| `/admin` | Admin overview | platformApi | PlatformShell; **no client role block** | API enforces admin (**F-04**) |
| `/shell` | Release shell | release-shell APIs | **No UI session gate** | Flag-gated backend (**F-03**) |

Loading/error handling generally present on product pages; no wholesale mock JSON in production pages (demo is server `demo_mode`).

---

## 8. Infrastructure and operations findings

| Topic | Finding |
|---|---|
| FastAPI | `ssri_model.api.app:app` |
| Postgres / Redis | Required for distributed mode; ready components ok locally |
| Celery | `ssri.execute_job` on `ssri_jobs` |
| Job persistence | DB store (distributed) / file store (local) |
| Idempotency | Header supported; Redis store in distributed |
| Lease recovery | Default **off**; compose `--profile recovery` |
| Env templates | `.env.example`, `frontend/.env.local.example` |
| Compose | `infra/docker-compose.yml` (+ staging overlay) |
| Prod vs local | `production_gate` strict only when `SSRI_API_ENVIRONMENT=production` |
| Staging | May skip production gate if env ≠ production (**F-05**) |
| Observability | Structured logs; no full APM required for local release |

Local healthy ≠ production hosting proven. Prior Nov 23 report addressed hosting readiness separately.

---

## 9. Security and reliability findings

| Topic | Evidence-based status |
|---|---|
| Auth enforcement | Fail-closed in production gate; local defaults auth off (intentional) |
| API keys | Admin-managed; tested |
| Admin/customer | Supabase `profiles.role`; RLS in migration |
| Upload / path safety | Geological + training zip traversal tests exist |
| CORS | Dev localhost defaults; prod needs explicit origins; no wildcard in prod |
| Rate limiting | Configurable; often off in local `.env.example` |
| Secrets | Service role server-only; anon keys public-by-design |
| Job cancel / ownership | Implemented |
| torch.load trust | Residual trusted-checkpoint risk (**F-06**) |

No speculative vuln claims beyond documented residual risks.

---

## 10. Test coverage and verification evidence

### Inventory

- **~115** `model/tests/test_*.py` files covering API, auth, jobs, geological, training, release shell, ML units.
- Frontend: `lib/conditioning.test.ts`, `productionIntegrity.test.ts`; e2e `browser-acceptance-gate.spec.ts`, `dashboard.spec.ts`, rehearsal spec.

### Reliable recorded evidence (not re-executed in this audit)

| Evidence | Result |
|---|---|
| Nov 23 browser acceptance | **READY FOR HOSTING** (`SSRI_PRE_DEPLOYMENT_BROWSER_ACCEPTANCE_REPORT.md`) |
| Abeokuta local completion | **READY WITH DOCUMENTED SCIENTIFIC LIMITATIONS** |
| Overlay commit tests (prior session) | overlay+conditioning **6 passed**; FE conditioning **6 passed** |
| Live ready probe (this audit) | infrastructure ok |

### Gaps

- No dedicated e2e for every platform admin/delete path.
- Documented historical flake: cancel-job under load (`POST_CONSOLIDATION_RELEASE_PREP.md`).
- Marketing pages have no contract tests tying copy to real routes.

Full Nov 23 gate and Abeokuta assess **not** repeated (no regression evidence).

---

## 11. Prioritised defect register

### F-01 — Marketing API / SDK fiction  
- **Severity:** P2  
- **Workflow:** Developers/platform marketing pages imply live `GET /v1/hazard` and installable SDKs.  
- **Evidence:** `frontend/app/developers/page.tsx`, `frontend/app/platform/page.tsx`; AGENTS.md explicitly says marketing copy is not implemented; real route is `POST /api/v1/assess`.  
- **Impact:** Client/operator confusion; false expectations.  
- **Minimal fix:** Relabel as roadmap or point to real `/api/v1/assess`.  
- **Tests:** None tying marketing to OpenAPI.

### F-02 — CORS methods vs platform DELETE  
- **Severity:** P2 (latent)  
- **Workflow:** Browser DELETE dataset if UI added.  
- **Evidence:** `app.py` `_configure_cors` allow_methods `GET,POST,OPTIONS`; `platform.py` `@router.delete(...)`; frontend has no DELETE caller.  
- **Impact:** Browser delete would fail preflight.  
- **Minimal fix:** Add DELETE to CORS when FE implements delete, or remove unused API.  
- **Tests:** Platform unit tests may hit API without browser CORS.

### F-03 — Operator `/shell` and `/training/operator` ungated in UI  
- **Severity:** P2  
- **Workflow:** Advanced training / release shell.  
- **Evidence:** Frontend audit — no `RequireSession`/`PlatformShell`; API still enforces permissions when auth on.  
- **Impact:** Local with auth off = open operator surface; with auth on = API protects.  
- **Minimal fix:** Wrap with session/operator gate for parity with dashboard.  
- **Tests:** API auth tests exist; FE gate tests thin.

### F-04 — Admin page relies solely on API 403  
- **Severity:** P3  
- **Workflow:** `/admin`  
- **Evidence:** PlatformShell without client `admin` redirect; API `role=admin` required.  
- **Impact:** Non-admins see error UX rather than hard nav block.  
- **Minimal fix:** Client-side role check mirroring workspace.  

### F-05 — Staging skips production_gate when env ≠ production  
- **Severity:** P2 (ops)  
- **Workflow:** Staging deploy misconfig.  
- **Evidence:** `production_gate.py` / compose staging notes in security explore.  
- **Impact:** Unsafe flags could slip on staging.  
- **Minimal fix:** Apply subset of gates to staging env.  

### F-06 — Checkpoint `torch.load` trust residual  
- **Severity:** P3  
- **Workflow:** Loading operator checkpoints.  
- **Evidence:** `docs/security_audit.md`; some paths `weights_only=False`.  
- **Impact:** Malicious checkpoint file risk if untrusted paths allowed.  
- **Minimal fix:** Prefer `safe_torch` / `weights_only` consistently.  

### F-07 — No dedicated assessment history UI/API list  
- **Severity:** P2  
- **Workflow:** “Assessment history” beyond in-session last result.  
- **Evidence:** Assess persists under `assessments/`; no list route; FE activity ≠ assess archive.  
- **Impact:** Operators cannot browse past AOI assesses in UI.  
- **Minimal fix:** Optional list endpoint + UI, or document filesystem-only retention.  

### F-08 — Lease recovery default off  
- **Severity:** P3  
- **Workflow:** Long jobs / worker crash.  
- **Evidence:** `SSRI_LEASE_RECOVERY_ENABLED=false`; recovery compose profile.  
- **Impact:** Stale RUNNING jobs until manual intervene.  
- **Minimal fix:** Enable recovery profile for distributed ops.

**Not defects:** `NOT_VALIDATED`; missing Abeokuta thickness/lineament vectors; synthetic checkpoint provenance; catalogue overlays not in 13-ch inference.

---

## 12. Completed capabilities (software)

- Live 13-channel AOI assessment with promoted checkpoint resolution  
- Geological catalogue ingest/validate/process/magnetic/activation/coverage  
- Abeokuta TMI provenance + assess geological context overlays (commit `4455877`)  
- Manual Stage 2.5 training + model activate  
- Platform v4 datasets/runs/models/activity/admin (Supabase)  
- Jobs async for inference/batch/training  
- Health/ready with infra components  
- Auth key management + production gate  
- Browser acceptance (Nov 23) + Abeokuta completion evidence  

---

## 13. Known scientific limitations

1. Scientific validation status remains **NOT_VALIDATED**.  
2. Active local checkpoint is synthetic/bootstrap Stage 2.5 weights.  
3. Scores are relative susceptibility rankings, not calibrated probabilities.  
4. Domain similarity often uncalibrated; CI bands may be degenerate.  
5. Abeokuta overburden thickness (m) and lineament vectors unavailable without external data.  
6. Catalogue overlays do not alter live 13-channel predictions.  
7. Marketing liquefaction ≠ live assess class (sinkhole).

---

## 14. Recommended minimal remediation sequence

1. **Copy hygiene (F-01):** Align `/developers` & `/platform` with `POST /api/v1/assess` or mark “not shipped.”  
2. **Operator UI gates (F-03):** Session-wrap `/training/operator` and `/shell`.  
3. **CORS/DELETE (F-02):** Decide keep API + CORS, or drop unused DELETE.  
4. **Assess history (F-07):** Document filesystem retention or add minimal list UI.  
5. **Ops (F-05, F-08):** Staging gate subset; enable recovery profile for distributed.  
6. **Hardening (F-06, F-04):** Checkpoint load safety; admin client gate.

Do **not** retrain or inject schema-v2 into live assess without an approved design.

---

## 15. Final local release decision

### **READY FOR LOCAL RELEASE**

Rationale: Authoritative stack is present and locally healthy; core assess + geological + training/platform paths are implemented and backed by recent acceptance evidence; no proven P0/P1 blockers for local operation. Scientific qualification remains limited and must stay disclosed.

**Not** a claim of production scientific readiness or that marketing SDKs exist.

---

**Stop.** No remediation performed. No commit/push/deploy. Awaiting approval before any fix work.
