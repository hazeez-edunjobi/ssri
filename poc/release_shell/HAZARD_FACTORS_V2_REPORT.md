# HAZARD_FACTORS_V2_REPORT (LOCAL ONLY — not pushed)

**Branch:** `feature/hazard-factors-v2`  
**Identity:** `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` · no Co-authored-by  
**Remote:** do not push (owner reviews and pushes later)

**Local tip (VERIFIED):** `848496803a10d0445087635065c42a6733219946`

```powershell
git rev-parse feature/hazard-factors-v2
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
Script: `scripts/check_abeokuta_overburden_units.py` → `outputs/abeokuta_overburden_unit_sanity.txt`

| Result | Value |
|--------|-------|
| status | FEATURE_LAYER_ONLY |
| value_min / max | −212.76 … 221.47 |
| UNIT_SANITY | **WARN — 11 250 negative value(s)** in `overburden_thickness` |
| Test | `test_overburden_thickness_flags_negative_z` |

---

## SYNTHETIC v2 e2e — per-seed gates (VERIFIED)

Source: `outputs/e2e_synthetic_v2/work/.../release_shell_evaluation.json`  
Seeds: **42, 43, 44**. Aggregate: all hazards **`trained, no demonstrated skill beyond slope`** (`seeds_passed=0`).

| Hazard | Seed 42 gate / ROC / ΔAUC vs slope | Seed 43 | Seed 44 |
|--------|-------------------------------------|---------|---------|
| subsidence | no skill beyond slope / 0.497 / −0.061 | 0.498 / −0.061 | 0.485 / −0.073 |
| landslide | no skill beyond slope / 0.523 / +0.082 | 0.447 / +0.006 | 0.494 / +0.052 |
| sinkhole | no skill beyond slope / ROC null | null | null |

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
