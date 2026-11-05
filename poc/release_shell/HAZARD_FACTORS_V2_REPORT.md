# HAZARD_FACTORS_V2_REPORT (LOCAL ONLY — not pushed)

**Branch:** `feature/hazard-factors-v2`  
**Identity:** `hazeez-edunjobi <ifeoluwasuccess520@gmail.com>` · no Co-authored-by  
**Remote:** do not push (owner reviews and pushes later)

**Local tip (VERIFIED):** `270788f981149182638bf403b3b964a747592d0a`

```powershell
git rev-parse feature/hazard-factors-v2
```

---

## Tasks 1–8 checklist

| Task | Status | Evidence |
|------|--------|----------|
| 1 Inspect client CSV | **DONE** | `CLIENT_CSV_FINDINGS.md`, `outputs/client_csv_inspect/findings.json` — VERIFIED |
| 2 Generic point-grid CSV | **DONE** | `release_shell/point_grid_csv.py` — CRS required, streaming, gaps, FEATURE_LAYER_ONLY |
| 3 Channel schema v2 | **DONE** | `release_shell/channel_schema.py` — v1 unchanged, v2 +3 channels; assess mismatch names missing channels |
| 4 Labels + joining | **DONE** | `release_shell/labels_inventory.py` + hazard registry; training refuse without labels (messages) |
| 5 Configurable spatial blocks | **DONE** | `spatial_split.py` + flags `SSRI_RELEASE_SHELL_BLOCK_SIZE_KM/DEG`; local evidence string |
| 6 Predictions / preview | **DONE** | `assess_contract.py` + `SSRI_PREVIEW_UNEVALUATED_SCORES` (default OFF); assess schema check |
| 7 Tests + rehearsal | **DONE** | `tests/test_hazard_factors_v2.py` (10); suite **142** OFF/ON; verify pass; frozen MATCH; rehearsal JSON |
| 8 Docs | **DONE** | `DATASET_SPEC.md`, `README_OWNER.md`, `OWNER_API_GUIDE.md`, `LIMITATIONS.md` |

**PARTIAL notes**

- Full end-to-end 3-seed train on a complete **v2** 16-channel Stage 2.5 ZIP was not re-run as a new multi-hour job; existing shell train path is unchanged and v1 Stage 2.5 still trains. Abeokuta-format path is proven FEATURE_LAYER_ONLY (cannot train on one layer alone) — VERIFIED.
- SYNTHETIC template ZIP for v2 not newly packaged binary; schema + docs describe the contract. Existing v1 SYNTHETIC template remains.

---

## Task 1 summary (VERIFIED)

| Item | Value |
|------|-------|
| File | `sheet 260_Abeokuta.csv` (only copy, ~10.1 MB) |
| Rows | 308 153 data + header `X,Y,Z` |
| Delimiter | comma |
| Spacing | 100 × 100 regular |
| Gaps | 7 129 missing cells |
| Duplicates | 0 |
| CRS / units / Z meaning | **UNKNOWN** — client must confirm |

---

## Test results (VERIFIED)

| Matrix | Result |
|--------|--------|
| Flag **OFF** | **142 passed** (prior 132 + 10 v2 tests) |
| Flag **ON** | **142 passed** |
| DeepSlide | included in 142 (9 not skipped when deps installed) |
| `scripts/verify.py` | `{"pass": true, ...}` |
| Frozen hashes | v1 `BD2A86BC` · v2 `5F63E362` · v3 `70FE823F` · manifest `E0D31A4F` (CRLF wt) **MATCH** |

---

## Rehearsal log (VERIFIED)

Script: `poc/release_shell/scripts/rehearse_hazard_factors_v2.py`  
Output: `poc/release_shell/outputs/hazard_factors_v2_rehearsal/rehearsal.json`

| Run | Result |
|-----|--------|
| SYNTHETIC 20×20 overburden CSV | FEATURE_LAYER_ONLY, ~0.02 s, ~259 MB RSS |
| SYNTHETIC labels | 25 landslide points parsed |
| REAL Abeokuta + ASSUMED-FOR-TEST `EPSG:32631` | FEATURE_LAYER_ONLY, cannot train, 308 153 rows, 7 129 gaps, ~3.2 s, ~317 MB RSS — **not real evidence** |

---

## Open client questions

1. What does Z measure?  
2. Units?  
3. Thickness vs depth-to-bedrock vs other?  
4. CRS (EPSG or WKT)?  
5. Are the 7 129 gaps intentional?  
6. How to treat negative Z values?

---

## Open risks

- Complete v2 training needs all 16 channels + labels + block size suitable for the AOI.  
- Assumed CRS for Abeokuta must not ship as fact.  
- `pyproj` added to model deps (3.7.2) for CRS/reproject.  
- Preview scores can be misread as validated — limitations always attached; default OFF.

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
