# SSRI — Final Branch Consolidation & Integration Readiness Report

**Date:** 2026-11-19  
**Consolidation branch:** `consolidate/ssri-integration-ready`  
**Verification-complete tip (suites + merges):** `3c5cb600cf2a269b5ef5a47e9e0ea4510c6e6055`  
**Backup of prior main:** tag `backup/main-pre-consolidation-e89fa03` → `e89fa03a4fbbe1a75198bd1d3bf62d4a5b02cfd0`  
**Remote push / deploy:** **not performed** (awaiting explicit confirmation)  
**Identity on consolidation commits:** hazeez-edunjobi \<ifeoluwasuccess520@gmail.com\> · no Co-authored-by  
**Flag default:** `SSRI_RELEASE_SHELL` remains **OFF**

Scientific validation remains **separate** from platform readiness. Results are **NOT_VALIDATED**. Abeokuta CRS/units remain ASSUMED-FOR-TEST / unconfirmed.

---

## 1. Branch inventory and merge decisions

| Branch | Unique vs `main` (at audit) | Purpose | Status | Decision |
|--------|----------------------------:|---------|--------|----------|
| finish/ssri-platform-rc2 | 22 | RC2 platform finish, hazard v2, shell UI, handoff | Complete | **MERGED** |
| finish/frontend-align-rc3 | 38 (18 beyond hazard) | Frontend↔backend align, geography, report, rehearsal | Complete | **MERGED** |
| feature/hazard-factors-v2 | 20 | Ancestor of both finish branches | Complete subset | Contained via finish branches |
| origin/feature/hazard-factors-v2 | diverged rewrite twin | Remote rewrite of local hazard | Duplicate history | **EXCLUDED** |
| backup/feature-hazard-factors-v2-pre-identity-rewrite | 20 | Backup snapshot | Snapshot | **EXCLUDED** |
| staging/ssri-shell-rc1 | 0 | Staging shell RC1 | Already in main | **EXCLUDED** |
| integration/ssri-shell-rc1 | 0 | Integration RC1 | Already in main | **EXCLUDED** |
| fix/upload-line-cap | 0 | Upload byte/line cap | Already in main | **EXCLUDED** |
| poc/release-shell | 0 | Original release shell | Already in main | **EXCLUDED** |
| poc/landslide-* | 0 | Research archives | Already in main | **EXCLUDED** |
| local-main-pre-rewrite / origin-main-snapshot | 0 | Obsolete pins | Obsolete | **EXCLUDED** |

**Stash preserved (not applied):** `stash@{0}` — *wip-frontend-align-rc3-before-rc2*

**Ancestry:** `main` → hazard tip `6a3eab6` → forked into RC2 (`1cfb91b`) and frontend-align (`73d6b7d`).

---

## 2. Consolidation summary

1. Tagged `backup/main-pre-consolidation-e89fa03`
2. Created `consolidate/ssri-integration-ready` from `main`
3. Fast-forward merged `finish/ssri-platform-rc2` → `1cfb91b`
4. Merged `finish/frontend-align-rc3`
5. Resolved conflicts; wrote Phase 1 audit + this report
6. Ran full verification gates (Phase 3)
7. Merged consolidation into local `main` only after gates (Phase 5)

---

## 3. Conflict-resolution summary

| Path | Resolution |
|------|------------|
| `PROGRESS.md` | Manual combine: consolidation header + frontend RC3 task notes + RC2 re-verify notes + historical pointer. Only true conflict. |
| `.gitignore` | Auto-merged; removed duplicate `poc/release_shell/outputs/recovery/` entry. Kept recovery ignore, measure-profile ignores, frontend_rehearsal ignore, Abeokuta CSV ignores. |

No conflicts in model protocols, assess contracts, auth, or job execution. Seed-meta embed fix from frontend-align (`job_workers.py`) retained.

---

## 4. Test results

### Backend full suite

| Command | Result |
|---------|--------|
| `cd model; poetry run pytest tests -q -rs --tb=line` (flag OFF) | **747 passed, 2 skipped** |
| same with `SSRI_RELEASE_SHELL=true` `SSRI_ASSESS_SOFTMAX=true` | **747 passed, 2 skipped** |

**Skipped (both runs):**
1. `tests/test_infrastructure_integration.py::test_readiness_with_real_services` — requires `SSRI_INTEGRATION_TESTS=1`
2. `tests/test_infrastructure_integration.py::test_postgres_job_lifecycle` — requires `SSRI_INTEGRATION_TESTS=1`

**Environment probe:** Redis `:6379` reachable; Postgres `:5432` **not** reachable → integration suite **not executed** (would still need env flag + DB URL).

Evidence: `poc/release_shell/outputs/consolidate_full_flag_{off,on}.txt`

### Curated suite

| Flag | Result |
|------|--------|
| OFF | **180 passed** |
| ON | **180 passed** |

Evidence: `poc/release_shell/outputs/consolidate_curated_flag_{off,on}.txt`

### Release verify

```text
python poc/release_shell/scripts/verify.py  → {"pass": true}
```

Evidence: `poc/release_shell/outputs/consolidate_verify_stdout.txt`, `verify_report.json`

### Frontend

| Command | Result |
|---------|--------|
| `npm run typecheck` | PASS (exit 0) |
| `npm run lint` | PASS (exit 0) |
| `npm run test` | **20 passed** |
| `npm run build` | PASS (Next.js 16.3.7) |

Evidence: `poc/release_shell/outputs/consolidate_frontend_*.txt`

### API smoke (TestClient, flag OFF)

| Endpoint | Result |
|----------|--------|
| `GET /health` | 200 `{"status":"ok","service":"ssri-inference"}` |
| `GET /api/v1/ready` | exercised (route registered under `/api/v1`) |
| `GET /api/v1/release-shell/status` with flag OFF | must report disabled / refuse shell ops (default OFF verified via `release_shell_enabled()==False`) |

### Not run / not claimed

| Item | Reason |
|------|--------|
| Distributed Postgres+Redis integration | Postgres unavailable locally; env flag unset |
| Hosted staging smoke (`smoke_staging.py` against live URL) | Staging URL/API key UNKNOWN |
| Playwright SYNTHETIC rehearsal re-run | Prior evidence on frontend-align tip committed under `outputs/frontend_rehearsal/`; full 3.5m re-run not repeated this consolidation |
| Production deploy | Explicitly out of scope without confirmation |

---

## 5. Final `main` commit SHA

- **Verification-complete tip** (all product merges + suite evidence): `3c5cb600cf2a269b5ef5a47e9e0ea4510c6e6055`
- **Authoritative local `main` tip** after documentation pins: recorded in the commit that lands this section (see `git rev-parse main` / log subject *Clarify final main SHAs…*).

Prior `main` before consolidation: `e89fa03a4fbbe1a75198bd1d3bf62d4a5b02cfd0` (tagged `backup/main-pre-consolidation-e89fa03`).
`origin/main` is still at that prior tip — **not pushed**.

---

## 6. Release-readiness report

| # | Area | Status | Notes |
|---|------|--------|-------|
| 1 | Code consolidation | **PASS** | Required finish branches merged; experimental/remote rewrite excluded |
| 2 | Frontend readiness | **PASS WITH WARNINGS** | typecheck/lint/test/build green; live auth against real Supabase not re-proven here; assess latency ~14s open item |
| 3 | API readiness | **PASS WITH WARNINGS** | Suites green flag OFF/ON; health OK; hosted CORS/rate-limit against real deploy NOT TESTED |
| 4 | Worker readiness | **PASS WITH WARNINGS** | Unit/local job paths covered by suite; Celery/Redis distributed path SKIPPED (no Postgres) |
| 5 | Database and storage readiness | **PASS WITH WARNINGS** | Code/migrations present; live Postgres lifecycle NOT TESTED this session |
| 6 | Geospatial upload/validation | **PASS WITH WARNINGS** | Validator/contracts/geography tests green; Abeokuta CRS/units still unconfirmed client data |
| 7 | Training workflow readiness | **PASS WITH WARNINGS** | Multi-seed + eval + promote paths covered by tests + prior rehearsal; live long train on client data NOT TESTED |
| 8 | Security and configuration | **PASS WITH WARNINGS** | Flag default OFF verified; secrets not committed; staging keys UNKNOWN; hosted auth smoke NOT TESTED |
| 9 | Deployment readiness | **BLOCKED** | No hosted deploy or staging smoke performed; checklist exists (`STAGING_DEPLOY_CHECKLIST.md`) |
| 10 | Scientific model validation | **NOT TESTED** / remains **NOT_VALIDATED** | Platform green ≠ geological skill; slope-baseline gates still apply |

---

## 7. Outstanding blockers

| Blocker | Impact | Action |
|---------|--------|--------|
| No staging URL / API key / Supabase / GEE | Cannot claim deploy readiness | Owner supplies staging secrets; run `smoke_staging.py` |
| Postgres not running locally | Distributed job persistence unproven this session | Start Compose Postgres; set `SSRI_INTEGRATION_TESTS=1` + DB/Redis URLs; re-run integration tests |
| Abeokuta CRS / units / provenance | Client data cannot be treated as validated inputs | Complete CRS confirmation, unit audit, provenance checklist before client demo of that dataset |
| Assess ~14s on SYNTHETIC 3-seed CPU | Demo UX slower than 10s target | Profile `mc_samples` / feature build; document expected latency |
| Scientific validation | Must not market as production geology | Keep NOT_VALIDATED; slope gates; no silent promotion of synthetic skill |

---

## 8. Deployment checklist (local → staging)

1. Clean tree on the final `main` SHA
2. Confirm `SSRI_RELEASE_SHELL` default OFF in code; enable only on intended staging service
3. Set staging env (API key, DB, Redis, storage, Supabase, GEE as needed)
4. Build frontend with staging `NEXT_PUBLIC_*` values
5. Deploy API + worker + frontend
6. Run `poc/release_shell/scripts/smoke_staging.py --base-url … --api-key …`
7. Confirm flag-OFF clients do not get shell routes; flag-ON shell upload→train→eval→assess works
8. Do **not** claim scientific validation

Full detail: `STAGING_DEPLOY_CHECKLIST.md`

---

## 9. Client demonstration checklist

1. Start from clean `main` build (API + frontend)
2. Show `/shell` with flag ON (staging): upload SYNTHETIC v2 template (not Abeokuta as “validated”)
3. Validate → show CRS/layer mapping UI; refuse silent EPSG:32631 assumption
4. Train 3 seeds → evaluate → show gate language (“trained, no demonstrated skill beyond slope” where applicable)
5. Promote eligible checkpoint → `/dashboard` map click 6 dp → assess → download HTML report
6. Show out-of-region withhold behaviour
7. Explicit disclaimer: **NOT_VALIDATED**, research-ready platform, not geological truth
8. If showing Abeokuta: label CRS/units as **unconfirmed** until client answers `handoff/CLIENT_QUESTIONS.md`

---

## Branches intentionally kept intact

Development branches were **not** deleted. Remote was **not** pushed.
