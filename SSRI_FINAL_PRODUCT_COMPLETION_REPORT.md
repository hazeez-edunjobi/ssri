# SSRI — Final Product Completion Report

**Date:** 2026-11-24  
**Sprint:** Final Product Completion (assessment history UI + R-09/R-10/R-11 + local verification)  
**Git HEAD:** `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` (`main`, ahead 1 of `origin/main`)  
**Commit / push / deploy / retrain / checkpoint change:** **not performed** — awaiting approval  
**Active checkpoint:** `ssri-model-e7af3afcd0` SHA256 `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` (unchanged)

---

## Executive verdict

Local product software for this sprint is **complete with documented limitations**. Assessment history works end-to-end in the browser against the live API. Staging production-gate subset, lease-recovery defaults, and product-path checkpoint loading are in place without weakening production security. Scientific validation remains **blocked by missing real subsidence ground truth**; production claims remain **not validated**.

| Dimension | Result |
|---|---|
| Assessment history UI | **Works** (list + detail + pagination) |
| Staging gate (R-09) | **Safe for staging subset** — demo/dev-auth/wildcard CORS blocked; full auth still production-required |
| Lease recovery (R-10) | **Safe default** — on for staging when unset; off for development/production unless explicit |
| Checkpoint loading (R-11) | **Safe on product paths** via `safe_torch`; PoC scripts remain out of path |
| Complete local application | **READY WITH DOCUMENTED LIMITATIONS** |
| Scientific validation | **NOT VALIDATED / BLOCKED BY MISSING DATA** |
| Production readiness | **NOT VALIDATED** |

---

## 1. What was implemented (this sprint)

### Assessment history frontend

- `/assessments` — list with hazard scores, confidence tiers, timestamps, coordinates (or honest missing location), pagination (`limit`/`offset`/`has_more`), loading / empty / error / retry.
- `/assessments/[id]` — detail from `GET /api/v1/assess/history/{id}`; notes and stored payload fields only; map deep-link when lat/lon exist.
- Client: `listAssessmentHistory` / `getAssessmentHistoryDetail` in `frontend/lib/api.ts` using existing `authHeaders`.
- Helpers + tests: `frontend/lib/assessmentHistory.ts` (+ `.test.ts`).
- Nav: Assessments link in `PlatformShell`; workspace linkage preserved.
- Session gate: `RequireSession` (same pattern as dashboard/workspace).

### R-09 — Staging production-gate subset

- `validate_staging_environment` in `production_gate.py`.
- Staging rejects: `SSRI_DEMO_MODE`, `SSRI_AUTH_DEVELOPMENT_MODE`, wildcard CORS.
- Staging does **not** force `SSRI_AUTH_ENABLED=true` (ops can qualify without full prod auth).
- Production gate unchanged (auth required, CORS explicit, JWT/bucket checks).
- Covered by `tests/test_production_gate.py`.

### R-10 — Distributed job lease recovery

- `_lease_recovery_enabled_from_env`: defaults **on** when `SSRI_API_ENVIRONMENT=staging` and flag unset; **off** for development/production unless explicit.
- Compose: `infra/docker-compose.yml` and `docker-compose.staging.yml` set recovery env for the recovery service; staging overlay documents ops qualification.
- **Ops note requiring approval:** enabling lease recovery in **production** still needs explicit `SSRI_LEASE_RECOVERY_ENABLED=true` plus the recovery process — not silently flipped for production.

### R-11 — Checkpoint loading

- Product/runtime loads use `ssri_model.ml.safe_torch.load_torch_checkpoint` (`weights_only=True` when supported): training checkpoint, evaluator, release-shell meta, bootstrap registry script.
- No remaining `torch.load` under `model/src/ssri_model` outside `safe_torch.py`.
- Residual unsafe loads remain only in **PoC / research scripts** (`poc/landslide*`) and unit tests that inspect saved files — **not** on the assess path.

### Preserved (not redone)

- 72 Abeokuta candidate magnetic lineaments and artefacts.
- Subsidence validation harness (missing-data honest block).
- Conditioning inventory + assess history API.
- F-01 / F-03 / F-04 frontend remediation.
- Active Stage 2.5 checkpoint and 13-channel architecture.

---

## 2. What was tested

| Check | Result |
|---|---|
| Frontend `npm test` | **94 passed** |
| `npx eslint app/assessments` | **PASS** (max-warnings 0) |
| `npx tsc --noEmit` | **PASS** |
| `npm run build` | **PASS** — routes include `/assessments`, `/assessments/[id]` |
| Backend `test_production_gate` + `test_assess_history` | **16 passed** |
| Prior geological suites (lineament, subsidence harness, overlay) | **PASS** (earlier in session) |
| `GET /api/v1/health` | **ok** |
| `GET /api/v1/ready` | **ready** — Postgres, Redis, queue ok; model NOT_VALIDATED |
| `GET /api/v1/assess/history` | **PASS** — total 7, pagination `has_more` |
| Geological conditioning + datasets | **PASS** (HTTP 200) |
| Docker `ssri-postgres` / `ssri-redis` | **healthy** |
| Celery worker | **running** (solo pool on `ssri_jobs`) |
| Frontend `:3000` | **200** including `/assessments` |
| Browser list `/assessments` | **PASS** — scores, coords, confidence visible |
| Browser detail `/assessments/assess-7dfc19ea9b27c4b7` | **PASS** — hazards, notes, checkpoint SHA, location provenance |
| Checkpoint SHA256 | **unchanged** `d912027e…e5d004` |

**Lint note:** repo-wide `npm run lint` still reports pre-existing `react-hooks/set-state-in-effect` on `RequireSession` / `PlatformShell` (not introduced by assessments; assessments pages use deferred load and lint clean).

---

## 3. Assessment history

**Works.** List and detail against live `GET /api/v1/assess/history` (+ `/{id}`). Fields displayed are only those returned by the API (no invented metrics). Pagination supported. Loading, empty, error, and retry states implemented.

---

## 4. Staging and recovery safety

**Staging gate:** safe subset applied — blocks demo mode, development auth, and wildcard CORS without silently imposing full production auth.  
**Lease recovery:** safe for staging default-on; production remains opt-in (requires explicit env + running recovery service). No silent production behaviour change.

---

## 5. Checkpoint loading safety

**Product paths safe** via `safe_torch`. PoC/research scripts remain unsafe by design and are out of the assess/inference path — document only; no retrain or checkpoint swap.

---

## 6. Complete local application

**Works with documented limitations:** API + FE + Postgres + Redis + Celery + assess archive + geological catalogue + Abeokuta candidates + assessment history. Scores remain relative rankings / NOT_VALIDATED.

---

## 7. Remaining scientific blockers

- **R-01** Real subsidence ground-truth inventory (absent on disk).
- **R-02** Independent Stage 2.5 scientific validation.
- **R-03** Geological QC of 72 candidate lineaments (not faults).
- **R-04** Overburden thickness (m) still unavailable.
- **R-05/R-06** Confirmed structures / lithology layers not implemented.
- **R-07** Injecting lineaments/overburden into inference requires new approved model (explicitly out of scope).

---

## 8. Remaining production blockers

- Scientific claims blocked by R-01/R-02.
- Production deploy still needs full production_gate compliance (auth on, explicit CORS, secrets) — not claimed complete by this local sprint.
- Enabling lease recovery in production requires **ops approval**.
- Marketing `/v1/hazard` / SDK copy remains roadmap-only (R-13 optional cleanup).
- Pre-existing FE lint noise on session/shell components.

---

## 9. Git status (no commit)

Branch: `main` ahead of `origin/main` by 1 (`4455877`). Working tree dirty with preserved user/sprint changes. **No commit, push, reset, clean, deploy, or retrain.**

See companion register and acceptance report for file inventory.

---

## Companion documents

- `SSRI_MASTER_COMPLETION_REPORT.md` (updated)
- `SSRI_REMAINING_WORK_REGISTER.md` (updated)
- `SSRI_FINAL_LOCAL_ACCEPTANCE_REPORT.md` (updated)
- Prior: lineament, subsidence, Abeokuta, FE remediation, whole-platform audit reports preserved

**Stop point:** local verification complete — awaiting human approval before commit.
