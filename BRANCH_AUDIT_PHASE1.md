# PHASE 1 — Repository & branch audit (READ-ONLY)

**Audit date:** 2026-11-19  
**Working tree:** clean on `finish/ssri-platform-rc2`  
**Current HEAD:** `1cfb91b858ce7ff0a12b77df34b284c8398fc6a2`  
**Local `main` tip:** `e89fa03a4fbbe1a75198bd1d3bf62d4a5b02cfd0` — *Merge staging/ssri-shell-rc1 into main…*  
**`origin/main`:** same as local `main` (`e89fa03`) — **VERIFIED**  
**Stash present:** `stash@{0}` — *On finish/frontend-align-rc3: wip-frontend-align-rc3-before-rc2* (preserved; not applied)  
**Remote:** `origin` → `https://github.com/hazeez-edunjobi/ssri.git`  
**No push / PR / deploy in this phase.**

---

## 1. Current state (VERIFIED)

| Item | Value |
|------|-------|
| Checked-out branch | `finish/ssri-platform-rc2` |
| Working tree | clean |
| Uncommitted / untracked | none (stash exists separately) |
| `main` vs `origin/main` | identical |
| Tags | `archive/credibility-v3-final`, `archive/due-diligence-final`, `archive/release-shell-final`, `archive/release-shell-rc`, `archive/ssri-shell-rc1` |

---

## 2. Ancestry map (VERIFIED)

```text
main (e89fa03)  ← already contains staging/release-shell (flag OFF default),
                  upload-cap, integration/ssri-shell-rc1, poc archives
   │
   └─ feature/hazard-factors-v2 (6a3eab6)   [20 commits ahead of main]
         │
         ├─ finish/ssri-platform-rc2 (1cfb91b)     [+2 re-verify commits]
         │
         └─ finish/frontend-align-rc3 (73d6b7d)    [+18 frontend/align commits]
```

`finish/ssri-platform-rc2` and `finish/frontend-align-rc3` **diverged** after `6a3eab6`. Neither is an ancestor of the other. Product consolidation that wants **both** RC2 platform finish **and** frontend alignment must merge both.

Local `feature/hazard-factors-v2` has **rewritten history** vs `origin/feature/hazard-factors-v2` (ahead 20 / behind 20). Same content lineage as backup tip `d66cb25`, different SHAs. Do **not** force-push.

---

## 3. Branch inventory

| Branch | Unique vs `main` | Purpose | Status | Recommendation |
|--------|----------------:|---------|--------|----------------|
| **finish/ssri-platform-rc2** | **22** | RC2: schema v2, shell UI owner inputs, handoff docs, smoke/runbook, FINISH_REPORT, re-verify 703/2 | **Complete** (platform RC2) | **MERGE** (primary) |
| **finish/frontend-align-rc3** | **38** (18 beyond hazard tip) | Frontend↔backend hazard/channel alignment, geography/CRS, assess report, Playwright SYNTHETIC rehearsal, STAGING_DEPLOY_CHECKLIST | **Complete** for frontend RC3 | **MERGE** after/with RC2 (required for coherent client UI) |
| feature/hazard-factors-v2 | 20 | Hazard-factors v2 + RC2 body (ancestor of both finish branches) | Complete subset | **SKIP as separate merge** — already contained via finish branches |
| origin/feature/hazard-factors-v2 | (diverged) | Remote rewritten twin of local hazard tip | Duplicate history | **SKIP** — do not merge remote tip; do not force-push |
| backup/feature-hazard-factors-v2-pre-identity-rewrite | 20 | Pre-identity-rewrite backup of hazard tip | Snapshot | **SKIP** — keep as backup ref only |
| staging/ssri-shell-rc1 | 0 | Staging release shell | **Already in main** | SKIP |
| integration/ssri-shell-rc1 | 0 | Integration RC1 | **Already in main** | SKIP |
| fix/upload-line-cap | 0 | Upload byte cap / 413 | **Already in main** | SKIP |
| poc/release-shell | 0 | Original release-shell introduction | **Already in main** | SKIP |
| poc/landslide-due-diligence | 0 | Frozen PROTOCOL v1 research | **Already in main** | SKIP (archive) |
| poc/landslide-credibility | 0 | Credibility v2 research | **Already in main** | SKIP (archive) |
| poc/landslide-credibility-v3 | 0 | Credibility v3 research | **Already in main** | SKIP (archive) |
| local-main-pre-rewrite | 0 | Old main snapshot | Obsolete | SKIP |
| origin-main-snapshot | 0 | Old origin/main pin | Obsolete | SKIP |

### Explicit sets

- **Required for product consolidation:** `finish/ssri-platform-rc2`, `finish/frontend-align-rc3`
- **Already integrated into `main`:** staging, integration, upload-cap, poc/release-shell, landslide poc archives
- **Experimental / research (keep separate, already archived on main):** landslide credibility / due-diligence (frozen protocols — do not edit)
- **Obsolete / snapshot:** `local-main-pre-rewrite`, `origin-main-snapshot`, `backup/feature-hazard-factors-v2-pre-identity-rewrite`
- **Valuable but needs merge care:** `finish/frontend-align-rc3` (diverged from RC2; product-critical UI/geography)

---

## 4. Recommended merge order

1. Tag / backup local `main` → e.g. `backup/main-pre-consolidation-<shortsha>`
2. Create `consolidate/ssri-integration-ready` from `main`
3. Merge `finish/ssri-platform-rc2` (fast-forward possible: main..rc2 linear, behind=0)
4. Merge `finish/frontend-align-rc3` (expect content conflicts on shared docs/PROGRESS)
5. Resolve conflicts by **keeping both product behaviours**: RC2 platform/docs + frontend alignment code
6. Do **not** merge remote `origin/feature/hazard-factors-v2` (history rewrite twin)
7. Leave stash untouched unless explicitly applied later

### Expected conflicts (VERIFIED probe)

`git merge-tree` of frontend-align into rc2 reports **`changed in both`** (at least two paths). Likely candidates from both sides editing:

- `PROGRESS.md`
- `FINISH_REPORT.md` / reports
- Possibly `.gitignore`, shell routes, or dashboard pages touched on both lineages after `6a3eab6`

RC2→main merge-tree: **no conflict markers** reported (clean linear add of 22 commits).

---

## 5. Missing functionality / integration risks

| Risk | Detail |
|------|--------|
| Client UI without frontend-align | Merging **only** RC2 leaves dashboard/shell without RC3 geography, report export, hazard registry alignment, embed-all-seeds meta fix |
| RC2 without RC3 meta fix | `6ef6871` embeds shell meta into **every** seed checkpoint — required so promoting non-primary seeds does not strip CRS |
| Hosted deploy not proven | No staging/prod smoke on a live host this audit; `smoke_staging.py` exists but needs human URL/key |
| Abeokuta CRS | Still ASSUMED-FOR-TEST — not scientific/product truth |
| Scientific validation | Remains `NOT_VALIDATED`; SYNTHETIC gates ≠ geological skill |
| Diverged remote hazard branch | Local and origin hazard tips differ by rewrite — consolidation must use **local** finish tips only |
| Distributed mode | Integration tests skip without `SSRI_INTEGRATION_TESTS=1` + Postgres/Redis |

---

## 6. Exact test commands after consolidation

```powershell
# Backend full suites
cd model
# Flag OFF
Remove-Item Env:SSRI_RELEASE_SHELL,Env:SSRI_ASSESS_SOFTMAX -ErrorAction SilentlyContinue
poetry run pytest tests -q -rs --tb=line

# Flag ON
$env:SSRI_RELEASE_SHELL='true'; $env:SSRI_ASSESS_SOFTMAX='true'
poetry run pytest tests -q -rs --tb=line

# Curated (use absolute path for deepslide)
poetry run pytest tests/test_api_assess.py tests/test_api_assess_audit.py `
  tests/test_demo_mode_assess.py tests/test_model_architecture.py `
  tests/test_multitask_model.py tests/test_inference.py `
  tests/test_evaluation_metrics.py tests/test_training_metrics.py `
  tests/test_release_shell_*.py tests/test_upload_row_cap.py `
  tests/test_hazard_factors_v2.py `
  ../poc/landslide4sense/integration/test_deepslide_engine.py -q --tb=line

# Release verify
cd ..
python poc/release_shell/scripts/verify.py

# Frontend
cd frontend
npm run typecheck
npm run lint
npm run test
npm run build

# Optional SYNTHETIC UI rehearsal (long)
npm run test:rehearsal
```

Document every skip (expect: `test_readiness_with_real_services`, `test_postgres_job_lifecycle` unless integration env set).

---

## 7. Gate to Phase 2

Phase 2 may proceed with this merge plan **only if approved**:

- Backup `main`
- Consolidate branch from `main`
- Merge `finish/ssri-platform-rc2` then `finish/frontend-align-rc3`
- Resolve conflicts deliberately
- No push / no deploy / no branch deletion

**Awaiting consolidation execution** (Phase 2 starts next unless stopped).
