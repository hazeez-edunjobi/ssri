# SSRI — Pre-Commit Review Report

**Date:** 2026-11-24  
**Mode:** Strictly read-only review (no stage / commit / push / deploy / reset / clean)  
**Branch:** `main` — ahead of `origin/main` by **1** (`4455877` local; `d8ac1bc` on origin)  
**HEAD:** `44558779ffe93a0f2a3d151e8f0a9d309f7e8753` — *Add honest catalogue overlays for lineament and overburden assess context.*  
**Working tree:** dirty (22 modified + 31 untracked paths at review start; this report adds one more untracked file)  
**Reviewer action:** await human approval  

---

## Final recommendation

# APPROVE COMMIT

Local software and documentation in the working tree are consistent with the final product completion claims. No secrets, `.env`, checkpoint weights, or `data/outputs/` artefacts appear in the commit candidate set. Active checkpoint SHA and the Stage 2.5 13-channel contract are unchanged. Soft defects remain (pre-existing FE lint noise; scientific blockers) but do **not** block a documentation + software commit.

---

## Verification checklist

| # | Check | Result |
|---|---|---|
| 1 | Every modified and untracked file inventoried | **PASS** |
| 2 | No accidental deletion / loss of previous work | **PASS** — `git ls-files --deleted` empty; diff name-status is all `M` (no `D`) |
| 3 | Implementation reports agree with source | **PASS** (minor soft docs gap on staging compose comment wording — see defects) |
| 4 | Tests / build evidence exists | **PASS** — terminal logs cited below |
| 5 | No secrets / `.env` / temp junk in candidate set | **PASS** |
| 6 | Active checkpoint SHA256 unchanged | **PASS** — `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` |
| 7 | 13-channel inference contract unchanged | **PASS** — `ml/constants.py` not in diff; `CHANNEL_NAMES` still 13 entries |
| 8 | Abeokuta lineaments + assessment evidence preserved | **PASS** — on disk under gitignored `data/outputs/` |
| 9 | Assessment history FE + API complete | **PASS** |
| 10 | F-01 / F-03 / F-04 remediation preserved | **PASS** |
| 11 | R-09 / R-10 / R-11 match documented security policy | **PASS** |
| 12 | Staging authentication policy explicitly documented | **PASS** — `production_gate.py` docstring + product reports; compose documents staging subset |

---

## Complete changed-file inventory

### Modified (tracked) — 22 files, +898 / −80 lines

| Path | Role |
|---|---|
| `frontend/app/admin/page.tsx` | F-01 admin gate (`RequireAdminAccess`) |
| `frontend/app/developers/page.tsx` | F-03 marketing API honesty (`marketingApiCopy`) |
| `frontend/app/geological/[id]/page.tsx` | Candidate lineament extract UI + honesty |
| `frontend/app/platform/page.tsx` | F-03 shared marketing copy |
| `frontend/app/shell/page.tsx` | F-01 operator gate |
| `frontend/app/training/operator/page.tsx` | F-01 operator gate |
| `frontend/app/workspace/page.tsx` | Assessments history link |
| `frontend/components/platform/PlatformShell.tsx` | Assessments nav entry |
| `frontend/lib/api.ts` | Assessment history client types + fetchers |
| `frontend/lib/geologicalApi.ts` | Lineament / geological client helpers |
| `infra/docker-compose.staging.yml` | Staging env + recovery always-on |
| `infra/docker-compose.yml` | Explicit lease-recovery env on recovery service |
| `model/src/ssri_model/api/app.py` | CORS includes `DELETE` |
| `model/src/ssri_model/api/geological_conditioning_overlay.py` | Candidate lineament overlay sampling |
| `model/src/ssri_model/api/production_gate.py` | Staging subset gate (R-09) |
| `model/src/ssri_model/api/routes/assess.py` | `GET /history` + `GET /history/{id}` |
| `model/src/ssri_model/api/routes/geological.py` | Lineament extract + conditioning routes |
| `model/src/ssri_model/geological/service.py` | Extract service wiring |
| `model/src/ssri_model/infrastructure/config.py` | Lease recovery default (R-10) |
| `model/src/ssri_model/release_shell/meta.py` | `safe_torch` loads (R-11) |
| `model/tests/test_production_gate.py` | Staging/production gate tests |
| `scripts/bootstrap_local_stage25_registry.py` | `safe_torch` load |

### Untracked — implementation, tests, reports, poc evidence

| Path | Role |
|---|---|
| `frontend/app/assessments/page.tsx` | History list UI |
| `frontend/app/assessments/[id]/page.tsx` | History detail UI |
| `frontend/components/auth/RequireAdminAccess.tsx` | F-01 admin gate component |
| `frontend/components/auth/RequireOperatorAccess.tsx` | F-01 operator gate component |
| `frontend/lib/assessmentHistory.ts` | History presentation helpers |
| `frontend/lib/assessmentHistory.test.ts` | History helper tests |
| `frontend/lib/marketingApiCopy.ts` | F-03 live vs roadmap copy |
| `frontend/lib/marketingApiCopy.test.ts` | F-03 tests |
| `frontend/lib/operatorAccess.ts` | F-01 access helpers |
| `frontend/lib/operatorAccess.test.ts` | F-01 tests |
| `model/src/ssri_model/evaluation/subsidence_validation.py` | Subsidence validation harness |
| `model/src/ssri_model/geological/conditioning_inventory.py` | Conditioning inventory |
| `model/src/ssri_model/geological/magnetic_lineament_extraction.py` | Candidate lineament extraction |
| `model/tests/test_assess_history.py` | History API + lease default tests |
| `model/tests/test_magnetic_lineament_extraction.py` | Extraction unit tests |
| `model/tests/test_subsidence_validation.py` | Missing-GT harness tests |
| `poc/abeokuta_candidate_lineament_summary.json` | 72-candidate summary evidence |
| `poc/abeokuta_final_local_completion_assess.json` | Assess evidence snapshot (~9 KB) |
| `poc/abeokuta_final_summary.txt` | Local completion notes |
| `poc/conditioning_factor_inventory.json` | Conditioning inventory dump |
| `poc/run_abeokuta_lineament_extraction.py` | Extraction runner script |
| `poc/subsidence_validation_missing_report.json` | Honest missing-GT report |
| `SSRI_FINAL_LOCAL_ABEOKUTA_COMPLETION_REPORT.md` | Abeokuta completion report |
| `SSRI_FINAL_LOCAL_ACCEPTANCE_REPORT.md` | Local acceptance |
| `SSRI_FINAL_PRODUCT_COMPLETION_REPORT.md` | Product sprint report |
| `SSRI_LINEAMENT_COMPLETION_REPORT.md` | Lineament report |
| `SSRI_MASTER_COMPLETION_REPORT.md` | Master report |
| `SSRI_REMAINING_WORK_REGISTER.md` | Remaining work |
| `SSRI_SUBSIDENCE_VALIDATION_REPORT.md` | Subsidence report |
| `SSRI_TARGETED_FRONTEND_REMEDIATION_REPORT.md` | F-01/03/04 report |
| `SSRI_WHOLE_PLATFORM_LOCAL_RELEASE_AUDIT.md` | Platform audit |
| `SSRI_PRE_COMMIT_REVIEW_REPORT.md` | **This file** (created by review) |

### Explicitly not in working-tree commit candidates (gitignored / absent from status)

| Path / class | Status |
|---|---|
| `.env`, `.env.local` | gitignored; **not** in `git status` |
| `credentials/*.json` | gitignored |
| `data/outputs/**` (checkpoints, assessments, lineament GeoTIFF/GeoJSON) | gitignored — **preserved on disk**, correctly excluded from Git |
| Active `best.pt` | Not staged; SHA verified on disk |

### Deletions

**None.** No deleted tracked files.

---

## Risk assessment

| Risk | Severity | Finding |
|---|---|---|
| Secret / credential leak in commit | Low | No `.env`, key stores, or JWT secrets in modified/untracked set. PoC JSON is scientific/ops evidence only. |
| Accidental overwrite of active checkpoint | None observed | SHA matches prior reports; registry `active.json` still `ssri-model-e7af3afcd0` |
| Weakening production auth | Low / controlled | Staging subset does **not** require `SSRI_AUTH_ENABLED`; production still requires it. Documented. |
| Silent production lease recovery | Low / controlled | Defaults off for production unless explicit env; staging defaults on. Compose recovery service explicit. |
| Unsafe checkpoint deserialization on product path | Low | Runtime paths use `safe_torch`; residual `torch.load` only in PoC/tests |
| Committing large rasters / weights | Mitigated | `data/outputs/` gitignored; untracked poc JSON files are small (≤ ~9 KB each) |
| Report / code drift | Low | Spot-checked history routes, staging gate, lease defaults, FE gates, 72 lineaments — agree |
| Pre-existing FE lint blocking CI | Soft | `RequireSession` / `PlatformShell` `set-state-in-effect`; assessments pages lint clean |

Overall commit risk: **acceptable for a local software + docs commit**.

---

## Test evidence (supporting artifacts)

Evidence is from completed agent terminals (not re-executed in this read-only review):

| Evidence | Source | Result |
|---|---|---|
| Backend production gate + assess history (+ lease defaults) | terminal `215138` | **16 passed** |
| Frontend unit tests | terminals `215134`, `215137` | **94 passed** |
| Assessments eslint (`max-warnings 0`) | `215134` / `215142` | **PASS** |
| `tsc --noEmit` | `215142` | **PASS** |
| `npm run build` (includes `/assessments`, `/assessments/[id]`) | `215134` | **PASS** exit 0 |
| Live API health / ready / history | `215140`, `215145` | **ok / ready / history paginated** |
| Geological conditioning + datasets + FE `/assessments` | `215141` | **200** |
| Postgres / Redis | `215141` | **healthy** |
| Browser history list + detail | prior product sprint session | **PASS** (documented in product/acceptance reports) |

**Note:** Terminal `215129` earlier failed repo-wide lint/typecheck (pre-existing session/shell lint + transitional assessments lint). Later focused runs superseded that failure. Do not treat `215129` as current truth.

---

## Checkpoint and contract

| Item | Value |
|---|---|
| Active model id | `ssri-model-e7af3afcd0` |
| `best.pt` SHA256 | `D912027E17ED532687F9D2A2C74FD3C18CA8C812AE49107D939ADE19DDE5D004` |
| Diff on `ml/constants.py` | **empty** (not modified) |
| `CHANNEL_NAMES` | 13 channels (elevation … magnetics) — Stage 2.5 contract intact |
| Overlay / lineament injection | Explicitly `used_in_inference=false` in code and QC |

---

## Abeokuta / assessment evidence (on disk, not in Git)

| Artefact | Observation |
|---|---|
| Lineament outputs | Present under `…/geo_be00a34ad6f4/working/derived/lineaments/` (geojson, density/distance/enhancement/ridge GeoTIFFs, preview PNG, QC JSON) |
| Candidate count | QC + `poc/abeokuta_candidate_lineament_summary.json`: **`n_lineaments`: 72**; `not_confirmed_faults_or_fractures: true`; `used_in_inference: false` |
| Assessment archive | **7** assessment directories under `data/outputs/assessments/` including `assess-7dfc19ea9b27c4b7` |

These remain local evidence; exclusion from Git is correct per `.gitignore`.

---

## Assessment history completeness

| Layer | Evidence |
|---|---|
| API list | `GET /api/v1/assess/history` in `assess.py` (`list_assessment_history`) |
| API detail | `GET /api/v1/assess/history/{assessment_id}` |
| FE client | `listAssessmentHistory` / `getAssessmentHistoryDetail` + types in `frontend/lib/api.ts` |
| FE UI | `/assessments`, `/assessments/[id]` with loading/empty/error/retry + pagination |
| Auth pattern | `RequireSession` + existing `authHeaders` |
| Nav | `PlatformShell` + workspace link |
| Tests | `model/tests/test_assess_history.py`, `frontend/lib/assessmentHistory.test.ts` |

---

## F-01 / F-03 / F-04 preservation

| Item | Evidence |
|---|---|
| F-01 operator/admin gates | `RequireOperatorAccess` / `RequireAdminAccess` wired on operator, shell, admin pages; helpers + tests present |
| F-03 marketing honesty | `marketingApiCopy` used by developers/platform; `/v1/hazard` roadmap-only |
| F-04 | Covered by targeted remediation report + productionIntegrity / related FE tests retained in suite |

---

## R-09 / R-10 / R-11 vs security policy

### R-09 Staging production-gate

- Code: `validate_staging_environment` rejects demo mode, auth development mode, wildcard CORS.
- Staging does **not** force `SSRI_AUTH_ENABLED=true`.
- Production still requires auth enabled + explicit CORS + related checks.
- Tests: `test_staging_rejects_demo_mode_and_dev_auth`, `test_staging_allows_auth_off_without_demo`.

### R-10 Lease recovery

- Default **on** only when `SSRI_API_ENVIRONMENT=staging` and flag unset.
- Development / production default **off** unless explicit.
- Production enable remains an **ops-approval** item (documented in config docstring + product report).
- Compose sets recovery env explicitly for the recovery service; staging overlay clears profile gate.

### R-11 Checkpoint loading

- Product paths: `safe_torch.load_torch_checkpoint` (release-shell meta, bootstrap script; trainer/evaluator already on helper).
- Residual raw `torch.load` limited to PoC/research scripts and tests — out of assess path.

---

## Staging authentication policy (explicit documentation)

Documented in:

1. **`model/src/ssri_model/api/production_gate.py`** — docstring: *“Full auth-enabled requirements remain production-only unless operators enable auth.”*
2. **`SSRI_FINAL_PRODUCT_COMPLETION_REPORT.md`** — staging does not force `SSRI_AUTH_ENABLED=true`.
3. **`SSRI_REMAINING_WORK_REGISTER.md`** — R-09: staging ≠ silent prod; full auth still prod-only.
4. **`infra/docker-compose.staging.yml`** header — staging subset: no demo, no auth development mode, no wildcard CORS (does not claim auth must be on).

**Policy statement for operators:**  
Staging may run with `SSRI_AUTH_ENABLED=false` for qualification, but must not use demo mode, development auth mode, or wildcard CORS. If staging enables auth, AuthConfig / key-store rules apply. Production still requires auth enabled.

Soft gap: staging Compose file does not spell out “auth may remain off” in one explicit sentence (policy is clear in gate code + reports). Non-blocking for commit.

---

## Files that should be excluded from the commit

| Exclude | Reason |
|---|---|
| `.env` / `.env.*` / credentials | Secrets — already gitignored; **do not force-add** |
| `data/outputs/**` (checkpoints, assessments, GeoTIFFs, large lineament rasters) | Generated / large / local — already gitignored; preserve on disk only |
| Any future `__pycache__`, `.next`, `node_modules` | Build junk — none currently in status |

**No mandatory exclusions** among the currently listed modified/untracked source, test, report, or small `poc/*.json|py|txt` evidence files.

**Optional hygiene (non-blocking):** `poc/abeokuta_candidate_lineament_summary.json` embeds a machine-local absolute `qc_relpath`. Safe to commit as evidence; operators may strip the absolute path later.

---

## Remaining defects

| ID | Severity | Defect | Blocks commit? |
|---|---|---|---|
| D-1 | Soft | Pre-existing `react-hooks/set-state-in-effect` on `RequireSession` / `PlatformShell` (repo-wide lint) | No |
| D-2 | Soft | Staging Compose comment could state auth-off-allowed more explicitly | No |
| D-3 | Soft | Absolute Windows path in poc lineament summary | No |
| D-4 | Scientific | R-01/R-02 missing real subsidence GT / validation | No (must not claim science validated) |
| D-5 | Ops | Production lease recovery still requires explicit enable + approval | No (documented; not silent) |
| D-6 | Informational | Earlier terminal `215129` failed; superseded by green later runs | No |

---

## Exact proposed commit scope

Include **all** of the following in one (or logically split) commit after human approval:

1. All **22 modified** tracked files listed above.  
2. All **untracked implementation / test / poc evidence / SSRI_*.md report** files listed above.  
3. **`SSRI_PRE_COMMIT_REVIEW_REPORT.md`** (this review).

Do **not** add:

- `.env`, credentials, `data/outputs/**`, checkpoint `.pt` files, rasters under geological working dirs.

Suggested commit message focus (for when approved):

> Complete local product sprint: assessment history UI, staging gate subset, lease-recovery defaults, safe checkpoint loads, geological lineament/subsidence tooling, and completion reports — without claiming scientific validation.

---

## Report ↔ source agreement summary

| Claim in product/master reports | Source confirmation |
|---|---|
| Assessment history UI + API | Present and wired |
| 72 Abeokuta candidate lineaments | QC + poc summary |
| Staging gate subset | `production_gate.py` + tests |
| Lease recovery staging default | `config.py` + tests + compose |
| `safe_torch` on product paths | `meta.py`, bootstrap script |
| Checkpoint SHA unchanged | Disk hash match |
| F-01/F-03 remediation | Components + page wiring + tests |
| CORS DELETE | `app.py` `allow_methods` |
| No retrain / no 13-ch change | constants not in diff; registry unchanged |

---

## Final decision

**APPROVE COMMIT** of the proposed scope after human approval.

Do not push, deploy, retrain, or promote checkpoints as part of that commit. Scientific validation remains **NOT VALIDATED / BLOCKED BY MISSING DATA**. Production readiness remains **NOT VALIDATED**.

**Awaiting human approval to stage/commit.**
