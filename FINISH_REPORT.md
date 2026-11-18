# FINISH_REPORT — SSRI platform "ready for first real upload" (RC2, LOCAL ONLY)

**Branch:** `finish/ssri-platform-rc2` (from local `feature/hazard-factors-v2`)  
**Verification tip:** see `git rev-parse HEAD` (do **not** pin a SHA here — it goes stale).  
**Identity:** `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` · no Co-authored-by  
**Remote:** **NOT pushed.** No PR. No deploy. No money spent.  
**Flag:** `SSRI_RELEASE_SHELL` stays default **OFF**; flag-off behaviour unchanged.

**Label key:** **VERIFIED** = reproduced with command/artefact · **REPORTED** = summarised · **UNKNOWN** = not established.

---

## 0. Status at a glance

| Task | Status | Headline evidence |
|------|--------|-------------------|
| 1 Close open verifications | **DONE** | tip unpinned; Abeokuta negative-Z → `UNIT_SANITY WARN` (overall=WARN, 11 250 negatives, min −212.76); SYNTHETIC v2 per-seed + aggregate gates |
| 2 `/shell` UI coverage | **DONE** | owner-input panel + 3 backend routes; UI-vs-API table §4; 3 env toggles remain API-only by design |
| 3 Host readiness | **DONE** | pyproj in lock; DeepSlide optional dry-run OK; upload/memory guidance measured; `smoke_staging.py` production guard |
| 4 Runbook + tooling | **DONE** | `RUNBOOK_FIRST_REAL_RUN.md`; `check_site_readiness.py`; Abeokuta block ESTIMATE |
| 5 Human-dependent docs | **DONE** | `poc/release_shell/handoff/` ×4 |
| 6 Final verification | **DONE** | §5 — full OFF/ON **703/2**, curated **151**, verify pass, frozen MATCH, identity clean, frozen/ckpt diffs empty |
| Deliverable | **DONE** | this file |

Nothing **NOT DONE**. Caveats in §7.

---

## 1. Branch / workspace

Created this session: `finish/ssri-platform-rc2` ← `feature/hazard-factors-v2` (`6a3eab6`).  
RC2 product work was already landed on `feature/hazard-factors-v2`; this branch re-verifies and records tip.

Diff vs local `main` (VERIFIED): frozen PROTOCOL/manifest and `*.pt` diffs are **EMPTY**.

---

## 2. Task 1 — Close open verifications (DONE)

### 1a Tip line (VERIFIED)
`poc/release_shell/HAZARD_FACTORS_V2_REPORT.md` instructs `git rev-parse HEAD` (no pinned SHA).

### 1b Abeokuta through real validator (VERIFIED, ASSUMED-FOR-TEST CRS)
Command: `poetry -C model run python ../poc/release_shell/scripts/check_abeokuta_overburden_units.py`  
CRS: **`EPSG:32631` (ASSUMED-FOR-TEST — not client-confirmed)** · layer `overburden_thickness`

| Result | Value |
|--------|-------|
| overall | **WARN** |
| unit_sanity | **WARN** — `UNIT_SANITY WARN: 11250 negative value(s)…` |
| value min / max | **−212.76** … 221.47 |
| gaps | WARN — 7 129 missing cells |
| trainable | False (FEATURE_LAYER_ONLY) |

Evidence: `poc/release_shell/outputs/abeokuta_overburden_unit_sanity.txt`

### 1c SYNTHETIC v2 per-seed + aggregate gates (VERIFIED, SYNTHETIC)
Source: `outputs/e2e_synthetic_v2/.../release_shell_evaluation.json` · dump: `outputs/rc2_e2e_gates.txt`  
Seeds **42, 43, 44**. Aggregate for all three hazards: **`trained, no demonstrated skill beyond slope`** (`seeds_passed=0`).

| Hazard | Seed 42 ROC / ΔAUC | Seed 43 | Seed 44 |
|--------|--------------------|---------|---------|
| subsidence | 0.497 / −0.061 | 0.498 / −0.061 | 0.485 / −0.073 |
| landslide | 0.523 / +0.082 | 0.447 / +0.006 | 0.494 / +0.052 |
| sinkhole | ROC null | null | null |

---

## 3. Tasks 3 & 4 — Host readiness, runbook (DONE)

### Measured upload/train profile (SYNTHETIC, LOCAL CPU) — VERIFIED
From `UPLOAD_CAP_REPORT.md` / `outputs/measure_upload_profile/profile.json` · 442 368 cells, 9 blocks, 27 tiles:

| Schema | Ch | validate | seed×3 wall (approx) | peak RSS |
|--------|----|----------|----------------------|----------|
| v1 | 13 | ~1.2 s | ~121 s total | **~452 MB** |
| v2 | 16 | ~1.4 s | ~111 s total | **~424 MB** |

**Recommended `SSRI_UPLOAD_MAX_BYTES`:** 1 GiB default; 512 MiB on ~2 GB RAM hosts. Oversize → **413**.

### Artefacts
- `poc/release_shell/scripts/smoke_staging.py` — production host refused unless explicit flag (exit 2) **VERIFIED**
- `poc/release_shell/RUNBOOK_FIRST_REAL_RUN.md`
- `poc/release_shell/scripts/check_site_readiness.py`
- Abeokuta block **ESTIMATE** (≈56×56 km): 5 km ≈132 · 10 km ≈42 · 20 km ≈12; default 50 km buffer infeasible here

### Lockfile (VERIFIED)
`pyproj` in main deps; DeepSlide optional group; `poetry install --with deepslide --dry-run --no-root` EXIT=0. Docker uses `--only main` (DeepSlide excluded from image by design).

---

## 4. Task 2 — `/shell` UI coverage (DONE)

| Owner input | UI? | Notes |
|-------------|-----|-------|
| ZIP upload | **UI** | Step 1 |
| Validation report | **UI** | Step 2 |
| Training progress | **UI** | Step 3 (poll) |
| Evaluation report | **UI** | Step 4 |
| Checkpoint selection | **UI** | Step 5 |
| Known limitations | **UI** | aside |
| CRS per layer | **UI** | required; never guessed |
| Layer naming / channel map | **UI** | datalist + schema details |
| Label inventory | **UI** | CRS required |
| Lineament vectors | **UI** | GeoJSON inspect |
| Block-size setting | **API-only** | read-only display; env (`OWNER_API_GUIDE.md`) |
| Schema version choice | **API-only** | read-only display |
| `preview_unevaluated_scores` | **API-only** | read-only display |

Fallback: `poc/release_shell/OWNER_API_GUIDE.md`.

---

## 5. Task 6 — Final verification (DONE, this session)

| Check | Result |
|-------|--------|
| Full FLAG **OFF** | **703 passed, 2 skipped** in 250.18 s (`outputs/rc2_full_flag_off.txt`) |
| Full FLAG **ON** | **703 passed, 2 skipped** in 201.79 s (`outputs/rc2_full_flag_on.txt`) |
| Curated OFF | **151 passed** in 43.29 s |
| Curated ON | **151 passed** in 54.53 s |
| `scripts/verify.py` | **`{"pass": true}`** |
| Frozen hashes | v1 `BD2A86BC` · v2 `5F63E362` · v3 `70FE823F` · manifest `E0D31A4F` — all **MATCH** |
| Diff vs `main` frozen / `*.pt` | **EMPTY** |
| Authors + committers `main..HEAD` | all `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` |
| Co-authored-by | **0** |
| Working tree | clean after this report commit |

**Skipped (named):**
- `test_readiness_with_real_services` (`tests/test_infrastructure_integration.py:65`)
- `test_postgres_job_lifecycle` (`tests/test_infrastructure_integration.py:71`)  
  Message: *Set SSRI_INTEGRATION_TESTS=1 to run distributed integration tests*

**Counts:** baseline expectation was 143 curated / 695 full; this tip has **+8** additive tests → **151 / 703**.

Curated command:

```text
poetry -C model run pytest tests/test_api_assess.py tests/test_api_assess_audit.py
  tests/test_demo_mode_assess.py tests/test_model_architecture.py tests/test_multitask_model.py
  tests/test_inference.py tests/test_evaluation_metrics.py tests/test_training_metrics.py
  tests/test_release_shell_softmax_contract.py tests/test_release_shell_spatial_split.py
  tests/test_release_shell_assess.py tests/test_release_shell_validator.py
  tests/test_release_shell_assess_contract.py tests/test_release_shell_assess_route.py
  tests/test_release_shell_jobs_result.py tests/test_upload_row_cap.py
  tests/test_hazard_factors_v2.py
  <abs>/poc/landslide4sense/integration/test_deepslide_engine.py -q --tb=line
```

---

## 6. Task 5 — Human-dependent artefacts (prepared, not faked)

Under `poc/release_shell/handoff/`:
- `CLIENT_QUESTIONS.md`
- `OWNER_STATUS.md`
- `REVIEW_REQUEST.md`
- `REMAINING_WORK_REGISTER.md`

---

## 7. Open items / caveats

1. Abeokuta CRS remains **ASSUMED-FOR-TEST** — client must confirm (`CLIENT_QUESTIONS.md`).
2. Block size / schema / preview toggles stay env-controlled (API-only in UI by design).
3. Fresh clean-room `poetry install` not re-run this session; prior dry-run EXIT=0 stands as REPORTED.
4. All gates/metrics here are **SYNTHETIC** / `NOT_VALIDATED`. First real model may show no skill beyond slope.

---

## 8. Commands for YOU to push / open a PR

This agent did **not** push.

```powershell
cd C:\Users\LENOVO\Documents\MrBusoye\ssri
git checkout finish/ssri-platform-rc2   # or feature/hazard-factors-v2
git rev-parse HEAD
git log --oneline main..HEAD
git status

git push -u origin finish/ssri-platform-rc2
gh pr create --base main --head finish/ssri-platform-rc2 `
  --title "SSRI RC2: ready for first real upload" `
  --body "See FINISH_REPORT.md. SSRI_RELEASE_SHELL stays default OFF. Local-only verification; not deployed."
```

---

## 9. Stop conditions

- Frozen hash mismatch → **none**  
- Test regression → **none** (703/2 OFF and ON; curated 151)  
- Push / remote / deploy / flag-off behaviour change → **none performed**
