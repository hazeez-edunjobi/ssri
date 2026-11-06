# HAZARD_FACTORS_V2_REPORT (LOCAL ONLY — not pushed)

**Branch:** `feature/hazard-factors-v2`  
**Identity:** `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` · no Co-authored-by  
**Remote:** do not push (owner reviews and pushes later)

**Local tip:** see `git rev-parse HEAD` (do **not** pin a SHA in this doc — it goes stale).

```powershell
git rev-parse HEAD
git status
```

---

## Tasks 1–8 checklist

| Task | Status | Evidence |
|------|--------|----------|
| 1 Inspect client CSV | **DONE** | `CLIENT_CSV_FINDINGS.md`, `outputs/client_csv_inspect/findings.json` — X/Y/Z mins/maxes, Z mean, histogram, negatives, gap clustering **VERIFIED** |
| 2 Generic point-grid CSV | **DONE** | `release_shell/point_grid_csv.py` — CRS required, streaming, gaps, FEATURE_LAYER_ONLY; **UNIT_SANITY** warns on negative `overburden_thickness` |
| 3 Channel schema v2 | **DONE** | schema-aware dataset/train/assess; SYNTHETIC v2 ZIP e2e (16 ch); assess returns `channel_schema_version=v2`; v1 input vs v2 ckpt names missing channels |
| 4 Labels + joining | **DONE** | `/jobs` → `VALIDATION_FAILED` with no labels (`test_release_shell_no_labels_route.py`) |
| 5 Configurable spatial blocks | **DONE** | `spatial_split.py` + block-size flags; local evidence string |
| 6 Predictions / preview | **DONE** | `assess_contract.py` + preview flag default OFF; assess schema check |
| 7 Tests + rehearsal | **DONE** | curated suite **143** OFF/ON; full suite **695 passed, 2 skipped** OFF/ON; `verify.py` pass; frozen MATCH; SYNTHETIC v2 e2e |
| 8 Docs | **DONE** | `DATASET_SPEC.md`, `README_OWNER.md`, `OWNER_API_GUIDE.md`, `LIMITATIONS.md` |

---

## Commits on this tip (local)

| SHA | Message |
|-----|---------|
| `54ac5bc` | Make Stage 2.5 train and assess honour channel schema v2 |
| `90318a2` | Refuse release-shell training without labels; warn on negative overburden |
| `a688c77` | Add SYNTHETIC schema-v2 Stage 2.5 template and end-to-end rehearsal scripts |
| `e352f8f` | Enrich CLIENT_CSV_FINDINGS with Z stats, histogram, and gap clustering |
| *(this tip)* | Record verification results in HAZARD_FACTORS_V2_REPORT |

---

## Task 1 summary (VERIFIED)

| Item | Value |
|------|-------|
| File | `sheet 260_Abeokuta.csv` (only copy, ~10.1 MB; **not committed**) |
| Rows | 308 153 data + header `X,Y,Z` |
| X min / max | −163 800 … −107 800 |
| Y min / max | 777 400 … 833 500 |
| Z min / max / mean | −212.76 … 221.47 / ~58.74 |
| Negative Z | **11 250** |
| Sentinel-like | **0** |
| Gaps | 7 129 — **clustered** (4 components; largest 1 952) |

---

## Abeokuta overburden unit sanity (VERIFIED)

CRS: **`EPSG:32631` (ASSUMED-FOR-TEST — not client-confirmed)**.  
Script: `scripts/check_abeokuta_overburden_units.py` → `outputs/abeokuta_overburden_unit_sanity.txt` (+ `.json`).  
Path: the **real file** now runs through `release_shell.validator.validate_point_grid_layer` (not just the CSV parser).

| Result | Value |
|--------|-------|
| overall (validator) | **WARN** |
| status / trainable | FEATURE_LAYER_ONLY / False |
| grid | 561 × 562, spacing 100 × 100 |
| value_min / max | −212.76 … 221.47 |
| `unit_sanity` check | **WARN — `UNIT_SANITY WARN: 11250 negative value(s) in layer 'overburden_thickness'`** |
| `gaps` check | WARN — 7 129 missing cell(s) |
| Tests | `test_layer_validator_surfaces_unit_sanity_warn`, `test_real_abeokuta_overburden_negative_z_warns` |

---

## SYNTHETIC v2 e2e — per-seed gates (VERIFIED)

**Source (VERIFIED):** `poc/release_shell/outputs/e2e_synthetic_v2/work/service-outputs/training/models/ssri-model-f589fdad75/release_shell_evaluation.json`
(log copy: `poc/release_shell/outputs/e2e_synthetic_v2/e2e_log.json` → `steps.*.evaluation_path`).
Seeds **42, 43, 44**; primary seed **42**. **SYNTHETIC** data — not real geography.

**Aggregate gate result (VERIFIED):** every hazard = **`trained, no demonstrated skill beyond slope`** with **`seeds_passed = 0`**.

| Hazard | Seed | gate | ROC AUC | ΔAUC vs slope | ΔAUC 95% CI |
|--------|------|------|---------|---------------|-------------|
| subsidence | 42 | no skill beyond slope | 0.4974 | −0.0610 | [−0.0674, −0.0581] |
| subsidence | 43 | no skill beyond slope | 0.4979 | −0.0605 | [−0.0654, −0.0573] |
| subsidence | 44 | no skill beyond slope | 0.4854 | −0.0731 | [−0.0938, −0.0559] |
| landslide | 42 | no skill beyond slope | 0.5233 | +0.0818 | [+0.0581, +0.1089] |
| landslide | 43 | no skill beyond slope | 0.4471 | +0.0056 | [−0.0298, +0.0444] |
| landslide | 44 | no skill beyond slope | 0.4937 | +0.0521 | [+0.0254, +0.0823] |
| sinkhole | 42/43/44 | no skill beyond slope | null | null | null |

**Reading it honestly:** landslide ΔAUC > 0 on all three seeds, but the gate still says *no demonstrated skill beyond slope* — a positive point estimate is not enough; the gate requires the gain to hold across seeds with a confidence interval that excludes zero (seed 43 CI crosses zero). Sinkhole has **insufficient labelled held-out pixels** (`status: insufficient_pixels`), so ROC is null and it cannot clear the gate. Subsidence is **worse** than slope on every seed.

Assess: v2 features → `channel_schema_version=v2`; v1 features → **400** naming `overburden_thickness, lineament_density, lineament_distance`.

---

## Test results on committed tip (VERIFIED)

Curated command (prior **142** + new overburden unit-sanity test → **143**):

```text
pytest tests/test_api_assess.py tests/test_api_assess_audit.py tests/test_demo_mode_assess.py
  tests/test_model_architecture.py tests/test_multitask_model.py tests/test_inference.py
  tests/test_evaluation_metrics.py tests/test_training_metrics.py
  tests/test_release_shell_softmax_contract.py tests/test_release_shell_spatial_split.py
  tests/test_release_shell_assess.py tests/test_release_shell_validator.py
  tests/test_release_shell_assess_contract.py tests/test_release_shell_assess_route.py
  tests/test_release_shell_jobs_result.py tests/test_upload_row_cap.py
  tests/test_hazard_factors_v2.py
  poc/landslide4sense/integration/test_deepslide_engine.py -q --tb=line
```

| Matrix | Result |
|--------|--------|
| Curated flag **OFF** | **143 passed** (`outputs/hf_v2_pytest_142_flag_off.txt`) |
| Curated flag **ON** | **143 passed** (`outputs/hf_v2_pytest_142_flag_on.txt`) |
| Full model flag **OFF** | **695 passed, 2 skipped** (~12 m) |
| Full model flag **ON** | **695 passed, 2 skipped** (~6.5 m) |
| Skipped tests | `test_readiness_with_real_services` · `test_postgres_job_lifecycle` (`SSRI_INTEGRATION_TESTS=1` required) |
| `scripts/verify.py` | **`{"pass": true}`** |
| Frozen hashes | v1 `BD2A86BC` LF **MATCH** · v2 `5F63E362` LF **MATCH** · v3 `70FE823F` LF **MATCH** · manifest `E0D31A4F` working-tree CRLF **MATCH** |

---

## Open client questions

1. What does Z measure?  
2. Units?  
3. Thickness vs depth-to-bedrock vs other?  
4. CRS (EPSG or WKT)?  
5. Are the 7 129 gaps intentional?  
6. How to treat negative Z values?

---

## Commands for you to review / push later

```powershell
cd C:\Users\LENOVO\Documents\MrBusoye\ssri
git checkout feature/hazard-factors-v2
git log --oneline main..HEAD
git status
# optional: push yourself when ready
git push -u origin feature/hazard-factors-v2
```

This agent did **not** push.
