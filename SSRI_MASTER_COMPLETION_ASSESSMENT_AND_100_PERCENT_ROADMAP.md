# SSRI — Master Completion Assessment & 100% Closure Roadmap

**Date:** 2026-11-21  
**Mode:** Read-only assessment (no source changes, commits, pushes, deploys, or Phase 6 activation)  
**Product:** SubSurface Risk Intelligence — *See the ground before you build.*  
**Tagline hazards:** subsidence · landslide · sinkhole  

---

## 1. Executive verdict

SSRI is a **research-ready software platform** with a pushed geological catalogue release on `main`, live hosts that expose geological routes and healthy distributed readiness, and an honest **NOT_VALIDATED** scientific posture. It is **not** a scientifically validated geological prediction product, and it is **not** production-qualified under the project’s own 100% definition.

| Metric | Verified estimate | Starting hypothesis | Delta |
|--------|------------------:|--------------------:|------|
| **Overall project completion** | **58%** | 70% | −12 pp (release/CI/deploy provenance and science weighted honestly) |
| **Engineering completion** | **81%** | ~90% | −9 pp (CI red, FE product gaps, observability/auth posture) |
| **Production release qualification** | **62%** | — | Feature-surface live; CI red; no deploy SHA; no authenticated smoke |
| **Scientific product maturity** | **34%** | ~40% | −6 pp (Phase 6 blocked; client geology unconfirmed; no evaluated v2 ckpt) |

**What 100% means here:** the definition in §13 / §14 of this assessment — including green CI, deploy provenance, authenticated production workflows, defensible geological data, independently evaluated model performance, and Phase 6 gates — **not** “the app loads.”

**Phase 6 (live v2 inference):** remains **BLOCKED**.

---

## 2. Verified repository and release state

### 2.1 Git / remote (re-verified this session)

| Check | Result |
|-------|--------|
| Branch | `main` |
| Local HEAD | `315b5eed218ec9605fab85d47e570e6cb4f561a6` |
| `origin/main` / `git ls-remote` | `315b5eed218ec9605fab85d47e570e6cb4f561a6` |
| Baseline `2890838…` ancestor | **Yes** |
| Commit A `e65929f…` present | **Yes** (parent of B) |
| Commit B `315b5ee…` = tip | **Yes** |
| Ahead/behind | Even (`## main...origin/main`) |

### 2.2 Working tree (not part of release commits)

| State | Paths |
|-------|--------|
| Modified tracked | `poc/release_shell/scripts/inspect_client_csv.py` (intentionally excluded from Commit A) |
| Untracked docs | `SSRI_GEOLOGICAL_RELEASE_EXECUTION_REPORT.md`, Abeokuta prep/audit docs |
| Untracked temps | `poc/_tmp_*`, `poc/release_shell/configs/` (incl. Abeokuta hypotheses) |

### 2.3 Release file presence

Commit A/B trees contain the approved geological package, FE `/geological`, tests/fixtures, and documentation pack including `SSRI_LIVE_V2_CONDITIONING_INTEGRATION_PLAN.md`. Client Abeokuta CSV and `.env` are **not** in `HEAD` trees as secret payloads (examples and POC unit-sanity artifacts exist; raw client CSV remains excluded).

### 2.4 Documentation vs code contradictions

| Document | Contradiction | Truth now |
|----------|---------------|-----------|
| `SSRI_FINAL_PROJECT_COMPLETION_REPORT.md` | Claims geological “uncommitted / not assumed deployed”; HEAD still `2890838` framing | Geological **committed + pushed** (`e65929f`/`315b5ee`); production OpenAPI mounts `/api/v1/geological/*` |
| `SSRI_MASTER_COMPLETION_BASELINE.md` | Geological “uncommitted” | Superseded by release |
| `SSRI_GEOLOGICAL_RELEASE_EXECUTION_REPORT.md` | Accurate for push/smoke; **untracked** (not in Commit B) | Local evidence only until separately committed |

### 2.5 Ruff / CI (re-verified)

| Item | Status |
|------|--------|
| Unused `fastapi.Form` | **Still present** — `model/src/ssri_model/api/routes/geological.py:7` |
| Unused `pathlib.Path` | **Still present** — `model/src/ssri_model/geological/service.py:8` |
| Local `poetry run ruff check` (geological paths) | **FAIL** (2× F401) |
| Local geological pytest | **PASS** — `35 passed, 1 skipped` |
| Frontend typecheck / `npm test` | **PASS** — typecheck 0; **31** tests |
| GitHub Actions tip run `44838126525` @ `315b5ee` | **failure** — frontend **success**; model **Ruff failure**; docker **skipped** |
| Recent `main` CI history | Multiple consecutive **failure** conclusions |

**Not resolved.** Fix requires a **new** owner-approved commit (do not amend A/B).

### 2.6 Production hosts (re-smoked this session)

| Endpoint | Result |
|----------|--------|
| `https://ssri-gamma.vercel.app/` | 200 |
| `https://ssri-gamma.vercel.app/geological` | 200 |
| `https://ssri-api.onrender.com/api/v1/health` | 200 `ok` |
| `https://ssri-api.onrender.com/api/v1/ready` | 200 — postgres/redis/queue **ok**, mode `distributed` |
| `GET /api/v1/geological/datasets` | 401 `AUTHENTICATION_REQUIRED` |
| `POST /api/v1/assess` | 401 `AUTHENTICATION_REQUIRED` |
| `GET /api/v1/release-shell/status` | 200 — shell **disabled**; `default_channel_schema=v1` (13); hazards 0/1/2; `NOT_VALIDATED` |

**Not obtained:** Vercel/Render deployment IDs, build timestamps, or stamped git SHA on the running image. Feature-surface ≠ cryptographic deploy provenance.

**Not exercised:** Authenticated catalogue CRUD, offline apply, assess response body, or Celery job completion (no production credentials used in this read-only pass).

---

## 3. Completion percentage breakdown

### 3.1 Workstream table

| Workstream | Verified % | Evidence | Remaining work |
|---|---:|---|---|
| Core software and architecture | **84** | FastAPI mounts assess/inference/batch/jobs/training/platform/geological/release-shell (`api/app.py`); jobs claim/idempotency/Celery (`jobs/`, `worker/`); production gate (`production_gate.py`); local pytest historically strong | Observability (metrics/tracing); public heavy endpoints; dual auth planes; lease recovery default-off; CI red |
| Geological ingestion and catalogue | **87** | Package + HTTP + 35/1 tests; depth≠thickness; NoData; bbox honesty; HTTP apply id-confined; ledger lock | FE offline-apply/original download; wire `nodata_policy`; APPLY_CONFLICT test; Ruff F401; auth prod smoke |
| Frontend and user workflows | **70** | Central clients (`lib/api.ts`, `geologicalApi.ts`, `platformApi.ts`); map assess + honest modal/report; geological CRUD UI; 31 FE tests | Assess history; API-key UI; session-aligned assess auth; gate `/shell` & `/training/operator`; marketing honesty; FE apply loop |
| Production infrastructure | **78** | Live ready=200 with redis/queue; compose topology; worker docs | Lease recovery ops; worker completion smoke; secret/env attestation; rate-limit multi-replica proof |
| Release and deployment verification | **55** | Push verified to `315b5ee`; unauth smoke; FE CI green | Model CI green; provider deploy SHA/IDs; authenticated smoke; execution report commit optional |
| Scientific data readiness | **38** | v1 channel pipelines exist; catalogue can hold client geology; Abeokuta **blocked** on CRS/Z/units/permission; lineaments **missing** | Client confirmation; labelled campaign data; lineaments; provenance permissions |
| Model scientific validation | **30** | 13-ch safety (`inference/safety.py`); `NOT_VALIDATED`; no evaluated 16-ch prod checkpoint; Phase 6 blocked | Spatial CV train/eval; baselines; calibration/uncertainty; independent review; only then versioned v2 path |

### 3.2 Three primary figures

**Engineering completion — 81%**  
Weighting within engineering only:

- Core architecture × 0.40 → 84  
- Geological software × 0.35 → 87  
- Frontend product engineering × 0.25 → 70  

\[
0.40(84)+0.35(87)+0.25(70)=33.6+30.45+17.5=81.55 \approx \mathbf{81\%}
\]

Credit is for **implemented + locally regression-tested** software. CI failure and missing prod auth smoke are **not** counted as engineering “done.”

**Production release qualification — 62%**  
Weighting:

- Runtime infrastructure health × 0.40 → 78  
- Release/deploy verification × 0.40 → 55  
- Authenticated operational workflows × 0.20 → **25** (gate only; workflows not verified)  

\[
0.40(78)+0.40(55)+0.20(25)=31.2+22+5=\mathbf{62\%}
\]

**Scientific product maturity — 34%**  
Weighting:

- Scientific data readiness × 0.45 → 38  
- Model validation / Phase 6 readiness × 0.55 → 30  

\[
0.45(38)+0.55(30)=17.1+16.5=\mathbf{33.6\%}\approx\mathbf{34\%}
\]

### 3.3 Overall project completion — 58%

Toward the §13 definition of 100% (software **and** production qualification **and** science **and** Phase 6):

| Pillar | Weight | Score | Contribution |
|--------|-------:|------:|-------------:|
| Engineering | 0.35 | 81 | 28.35 |
| Production qualification | 0.25 | 62 | 15.50 |
| Scientific maturity | 0.40 | 34 | 13.60 |
| **Overall** | 1.00 | | **57.45 ≈ 58%** |

**Why not ~70%:** the prior hypothesis over-credited “hosts respond” as release qualification and under-weighted (a) red CI, (b) missing deploy provenance, (c) blocked science/Phase 6 in the official 100% definition. Software completeness alone would look ~80%; the **product** definition of done does not.

### 3.4 Distinguishing credit types

| Kind | Geological catalogue | Live assess | 16-ch Phase 6 |
|------|----------------------|-------------|---------------|
| Implemented | Yes | Yes (13-ch) | Offline stack only |
| Locally tested | Yes (35/1) | Broad unit suite (prior) | Partial apply tests |
| Deployed (feature-surface) | Yes (OpenAPI/FE) | Yes | **No live path** |
| Operational (auth verified) | **No** | **No** (this pass) | N/A |
| Scientifically validated | **No** | **No** (`NOT_VALIDATED`) | **BLOCKED** |
| Independently verified | Audit docs exist; not external peer review | No | No |

---

## 4. Engineering versus scientific maturity

| | Engineering | Science |
|--|-------------|---------|
| Question answered | “Does the system implement intended workflows safely?” | “Are predictions defensible for ground decisions?” |
| Current answer | Largely yes for Stage 2.5 + catalogue software | No — research / susceptibility aid only |
| Key evidence | Routes, tests, safety channel checks, honest UI copy on dashboard | No evaluated production metric gate; client geology unconfirmed; Phase 6 blocked |
| Risk if conflated | Shipping a polished UI that users treat as validated geology | — |

---

## 5. Production qualification assessment

| Criterion | Status |
|-----------|--------|
| Hosts up | **Pass** (FE/API) |
| Distributed ready | **Pass** (postgres/redis/queue) |
| Auth enforced on assess/geo | **Pass** (401 without credentials) |
| CI green | **Fail** (Ruff) |
| Deploy SHA provenance | **Fail** (unavailable) |
| Authenticated E2E | **Fail / not run** |
| Worker job completion | **Not verified** |
| Lease recovery always on | **Fail** (opt-in profile) |
| Observability | **Weak** |

**Verdict:** **Partially qualified for research hosting; not release-qualified for “100% production” claims.**

---

## 6. Geological catalogue assessment

**Software maturity: high (≈87%). Product loop: incomplete.**

Enforced distinctions (code + tests; see audit):

- `depth_to_bedrock` ≠ `overburden_thickness` (`validate.py`, `apply.py`, shell validator).  
- Missing lattice → `FEATURE_NODATA`, not zero-fill.  
- Negatives → WARN / not silently abs-corrected.  
- Multi-dataset same measurement → conflicts; apply `APPLY_CONFLICT`.  
- Coverage metric = bbox intersection, explicitly not valid-cell.  
- `created_by_key_id` audit-only; shared-catalogue tenancy.  
- HTTP apply: registered `target_dataset_id`; `allow_direct_target_root` **not** in OpenAPI/`ApplyBody`.  
- SHA256 originals, path confinement, ledger lock, PASS-report recovery.

Gaps:

- FE cannot call offline apply / original download.  
- `nodata_policy` stored but not wired into ingest.  
- Ruff unused imports break CI.  
- Production authenticated catalogue workflows unverified.

---

## 7. Scientific data readiness

| Domain | Status |
|--------|--------|
| DEM / terrain / hydrology / vegetation indices | Pipeline exists; live AOI depends on GEE/OpenTopo config |
| Gravity / magnetics | Partial; path/config dependent |
| Overburden thickness (client) | **Blocked** — Abeokuta CRS/Z/units/negatives/spacing/permission unconfirmed |
| Lineaments | **Missing** for client AOI |
| Labels / ground truth | Contract exists; campaign-quality inventories not established for production claims |
| Live assess ← geological catalogue | **Not wired** (correct) |

Do **not** assume EPSG:32631, Z=thickness, or negative-Z-as-error.

---

## 8. Model validation status

| Item | Status |
|------|--------|
| Live contract | Stage 2.5 **13** channels (`CHANNEL_NAMES` / `CHANNEL_COUNT`; `inference/safety.py` rejects mismatch) |
| Hazards | subsidence (0), landslide (1), sinkhole (2) |
| Schema v2 (16) | Defined offline; can expand stacks |
| Evaluated 16-ch production checkpoint | **None evidenced** |
| Scientific status | **NOT_VALIDATED** |
| Foundation `.pt` in tree | Research artifacts (`models/ssri-foundation-v*.pt`) — **not** assess Stage 2.5 production validation |
| Historical scorecard gates | Failed / incomplete (`docs/SSRI_COMPLETION_SCORECARD.md`) |

---

## 9. Phase 6 gate status — BLOCKED

Live v2 inference must **not** activate until **all** pass:

1. Client/data confirmation for geological channels.  
2. Schema-matched checkpoint metadata.  
3. Reproducible training provenance.  
4. Defensible spatial train/val/test (leakage controlled).  
5. Baselines (13-ch, terrain-only, etc.) with per-hazard metrics.  
6. Calibration / uncertainty evaluation.  
7. Versioned inference path + rollback to v1.  
8. Safety tests for schema-v2 path.  
9. Explicit owner approval to change production channel contract.

**Current:** **BLOCKED.** Do not pad/trim/zero-fill channels into the 13-ch checkpoint. Do not claim catalogue layers influence live assess scores.

---

## 10. Outstanding-work register

### Immediate release blockers

| ID | Pri | Workstream | Description | Files / services | Deps | Acceptance | Verify | External? | Approval |
|----|-----|------------|-------------|------------------|------|------------|--------|-----------|----------|
| R1 | P0 | Release | Remove unused imports; green model CI | `api/routes/geological.py`, `geological/service.py` | None | Ruff clean; CI model+docker green on tip | `poetry run ruff check src tests`; Actions | No | **Yes** (new commit) |
| R2 | P0 | Prod qual | Capture deploy provenance after CI green | Vercel, Render | R1 | Deploy ID + git SHA recorded | Provider dashboards / CLI | Creds | **Yes** |
| R3 | P0 | Prod qual | Authenticated production smoke | FE, API, worker | Creds, R2 | Catalogue CRUD; apply requires `target_dataset_id`; assess 13-ch; job completes | Private smoke script (no secret logging) | **Creds** | **Yes** |

### Engineering completion

| ID | Pri | Workstream | Description | Files | Deps | Acceptance | Verify | External? | Approval |
|----|-----|------------|-------------|-------|------|------------|--------|-----------|----------|
| E1 | P1 | Geological FE | Wire offline apply + original download in UI | `geologicalApi.ts`, `geological/[id]/page.tsx` | Auth | Operator can apply to registered dataset; download original | FE manual + API tests | No | Yes |
| E2 | P1 | Geological | Wire `nodata_policy` into ingest | `service.py`, `point_grid_csv.py` | None | Declared policy affects ingest | pytest | No | Yes |
| E3 | P1 | Geological | `APPLY_CONFLICT` unit test | `test_geological_*.py` | None | Dual thickness apply fails | pytest | No | Yes |
| E4 | P1 | Frontend | Session-aligned assess auth (or documented key UX) | `lib/api.ts`, dashboard | Platform design | Logged-in assess without brittle env-only key | E2E | Possibly Supabase | Yes |
| E5 | P1 | Frontend | Gate `/shell` and `/training/operator` | layouts / `RequireSession` | None | Unauthenticated access redirected | Playwright | No | Yes |
| E6 | P2 | Frontend | Assessment history persistence | platform API + FE | Backend store | Reopen past assesses | E2E | Possibly DB | Yes |
| E7 | P2 | Frontend | API-key management UI | auth keys API + FE | Admin role | Create/list/disable keys | Manual | No | Yes |
| E8 | P2 | Core | Metrics/tracing + request IDs | `api/app.py`, worker | Infra | Ops can see queue/auth/error rates | Staging dashboards | Observability stack | Yes |
| E9 | P2 | Core | Auth on heavy public surfaces / rate limits | `layers.py`, etc. | Design | No unauthenticated heavy DoS path | Security tests | No | Yes |
| E10 | P2 | Product | Align marketing (`/developers`,`/platform`,`/hazards`) with real `/api/v1` + NOT_VALIDATED | FE marketing pages | Copy approval | No fake SDK/endpoints; no “risk/chance” overclaim | Review + wording tests | No | Yes |
| E11 | P2 | Docs | Commit or discard stale completion docs / execution report | root `SSRI_*.md` | Owner | Docs match `315b5ee` reality | git status | No | Yes |

### Production qualification

| ID | Pri | Workstream | Description | Deps | Acceptance | External? | Approval |
|----|-----|------------|-------------|------|------------|-----------|----------|
| P1 | P1 | Infra | Enable/verify lease recovery in production | Compose/Render worker | Stale RUNNING jobs recovered | Ops | Yes |
| P2 | P1 | Infra | Worker completion smoke with real job | R3 | Job → completed | Creds | Yes |
| P3 | P2 | Security | Confirm prod `SSRI_AUTH_ENABLED`, CORS, no dev auth | Render env | Gate checklist | Ops | Yes |
| P4 | P2 | Reliability | Load/soak + backup restore drill | — | Documented evidence | Ops | Yes |

### Scientific data readiness

| ID | Pri | Description | External? | Approval |
|----|-----|-------------|-----------|----------|
| S1 | P0 | Client confirms Abeokuta CRS, Z semantics, units, negatives, spacing, permission | **Client** | Yes |
| S2 | P0 | Obtain or formally waive lineament vectors | **Client / acquisition** | Yes |
| S3 | P1 | Campaign labelled inventories with CRS/dates/classes + spatial holdout plan | Domain expert | Yes |
| S4 | P1 | Document gravity/magnetics provenance for target AOIs | Data steward | Yes |

### Model scientific validation

| ID | Pri | Description | External? | Approval |
|----|-----|-------------|-----------|----------|
| M1 | P0 | Train/eval Stage 2.5 with spatial CV; log config/seeds | Compute + labels | Yes |
| M2 | P0 | Per-hazard metrics vs baselines; calibration/uncertainty | Analyst | Yes |
| M3 | P0 | Independent evaluation / review record | External preferred | Yes |
| M4 | P1 | Only promote checkpoints that beat/defend utility vs baselines | Owner science sign-off | Yes |

### Final live-v2 integration

| ID | Pri | Description | Deps | Approval |
|----|-----|-------------|------|----------|
| V1 | P0 | Keep Phase 6 **BLOCKED** until S* + M* pass | S1–S2, M1–M4 | Standing |
| V2 | — | Versioned 16-ch loader + safety + rollback to 13-ch | V1 gates | **Owner** |
| V3 | — | Prod regression: no silent catalogue→assess coupling | V2 | Owner |
| V4 | — | Update docs/UI to describe actual deployed schema | V2–V3 | Owner |

---

## 11. Dependencies and external blockers

| Blocker | Blocks | Owner |
|---------|--------|-------|
| Client CRS/Z/units/permission | Scientific use of Abeokuta overburden | Client |
| Missing lineaments | v2 lineament channels | Client / acquisition |
| Production auth credentials for smoke | Prod qualification R3/P2 | Ops |
| Provider dashboard/CLI access | Deploy provenance R2 | Ops |
| Labelled spatial datasets + compute | Model validation M* | Science + eng |
| Owner approval for new commits / Phase 6 | R1, V2 | Owner |

---

## 12. Prioritised roadmap to 100%

```text
Phase 0 — Stabilize release (engineering/ops)
  R1 Ruff → green CI → R2 deploy provenance → R3 authenticated smoke
  E1–E3 geological FE/tests polish
  E5/E10 honesty & auth gates on operator/marketing surfaces

Phase 1 — Production qualification
  P1–P3 recovery, worker proof, env attestation
  Overall target after Phase 0–1: Engineering ~90%, Prod qual ~85%, Overall ~65%
  (Science still ~34%)

Phase 2 — Scientific data
  S1–S4 client confirmation + labels + geophysics provenance
  Scientific maturity → ~55–65% if data arrives; else remains blocked

Phase 3 — Model validation (still NOT live v2)
  M1–M4 evaluation programme on correct schema
  Scientific maturity → ~80% only with independent evidence

Phase 4 — Phase 6 (only if gates pass)
  V2–V4 versioned live v2 + rollback + docs
  Then Overall → 100% under §13 definition
```

If external data/confirmation never arrives, **honest ceiling** is approximately:

- Engineering ~90–92%  
- Production qualification ~85–90%  
- Scientific maturity **stuck ~35–45%**  
- **Overall ~65–70%** — not 100%

---

## 13. Exact acceptance criteria for final completion

SSRI is **100% complete** only when **all** are true:

1. Core software implemented and regression-tested; **CI green** (model + frontend + docker).  
2. Geological catalogue secure and operational (HTTP confinement, provenance, FE apply loop).  
3. Frontend workflows complete and usable (assess, geological, training path clarity, auth gates).  
4. Production infrastructure stable (ready, recovery, worker proof).  
5. Deployment provenance verified (provider IDs + matching git SHA).  
6. Authenticated production workflows pass (catalogue, apply, assess, jobs).  
7. Geological datasets for intended AOIs have defensible CRS/units/provenance/permissions.  
8. Training/eval datasets scientifically appropriate with spatial separation.  
9. Model independently evaluated vs baselines; per-hazard performance and uncertainty defensible.  
10. Production model uses correct schema/checkpoint; status no longer falsely “validated.”  
11. Phase 6 gates passed **or** explicitly waived with permanent v1-only product scope (owner decision).  
12. Live integration (if any) passes regression; docs match deployed system.  

**Today:** criteria 1 (partial—CI red), 2 (partial—FE apply/auth smoke), 3–6 incomplete, 7–11 **failed/blocked**.

---

## 14. Evidence references

| Evidence | Location / command |
|----------|-------------------|
| Release commits | `e65929fe…`, `315b5eed…`; `git ls-remote origin refs/heads/main` |
| Execution report | `SSRI_GEOLOGICAL_RELEASE_EXECUTION_REPORT.md` (untracked) |
| Ruff failures | `geological.py:7` Form; `service.py:8` Path |
| Geological tests | `poetry run pytest tests/test_geological_*.py` → 35 passed, 1 skipped |
| FE tests | `npm run typecheck`; `npm test` → 31 pass |
| CI | Actions run `44838126525` — frontend success, model Ruff failure |
| Prod smoke | health/ready/geo 401/assess 401/shell status (this session) |
| 13-ch safety | `model/src/ssri_model/inference/safety.py`; `ml/constants.py` |
| Apply confinement | `api/routes/geological.py` `apply_offline`; `geological/target.py` |
| Science blockers | `SSRI_SCIENTIFIC_DATA_READINESS_REPORT.md`, `SSRI_MODEL_SCIENTIFIC_VALIDATION_REPORT.md` |
| Phase 6 plan | `SSRI_LIVE_V2_CONDITIONING_INTEGRATION_PLAN.md` |
| Architecture | `SSRI_GEOLOGICAL_CSV_INGESTION_ARCHITECTURE.md` |

---

## Closing statement

**SSRI is approximately 58% complete today** under a definition that requires engineering, production qualification, and scientific maturity together. Engineering alone is about **81%**; production qualification about **62%**; scientific maturity about **34%**.

**What prevents 100%:** (1) red CI from two unused imports; (2) missing deploy provenance and authenticated production E2E; (3) unfinished product loops (geological apply UI, assess history, auth consistency, marketing honesty); (4) unconfirmed client geology and missing lineaments; (5) absence of an independently evaluated production model; (6) Phase 6 remaining correctly **BLOCKED**.

**Exact sequence to close the gap:** fix Ruff → green CI → verify deploy SHA → authenticated smoke → FE/product hardening → client data confirmation → scientific train/eval programme → only then owner-approved Phase 6 / live v2. Without external scientific inputs, the project can approach engineering/ops ceilings but **cannot honestly reach 100%**.
