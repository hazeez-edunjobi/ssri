# SSRI — Repository-Wide Ruff CI Remediation Report

**Date:** 2026-11-21  
**Target CI commit:** `d06878699f398a3b364a3ce48498c9cc0149786d`  
**Workflow run:** [44881340836](https://github.com/hazeez-edunjobi/ssri/actions/runs/44881340836) (`failure` on model/Ruff)  
**Local HEAD during remediation:** `d06878699f398a3b364a3ce48498c9cc0149786d` (Commit C preserved)  
**Mode:** Implementation + verification only — **no stage / commit / push / deploy**

---

## Executive verdict

All **33** Ruff violations from `poetry run ruff check src tests` are resolved locally. Final check: **All checks passed** (`RUFF_FINAL=0`). Full backend suite: **828 passed, 3 skipped**. Authentication paths from Commit C were **not modified**.

---

## 1. All 33 original violations

| # | Location | Code | Issue |
|--:|----------|------|-------|
| 1–6 | `src/ssri_model/api/app.py:15,17,18,24,25,37` | E402 | Module-level import not at top of file (`load_dotenv` between imports) |
| 7 | `src/ssri_model/attribution/__init__.py:10` | F401 | Unused `typing.Any` |
| 8 | `src/ssri_model/attribution/__init__.py:10` | F401 | Unused `typing.Sequence` |
| 9 | `src/ssri_model/dann/train_step.py:9` | F401 | Unused `torch.nn` |
| 10 | `src/ssri_model/data/feature_engineering.py:372` | F401 | Unused `rasterio.transform.from_bounds` (in sampleRectangle helper) |
| 11 | `src/ssri_model/evaluation/evaluator.py:9` | F401 | Unused `typing.cast` |
| 12 | `src/ssri_model/manual_training/validation.py:14` | F401 | Unused `CHANNEL_COUNT` |
| 13 | `src/ssri_model/manual_training/validation.py:14` | F401 | Unused `CHANNEL_NAMES` |
| 14 | `src/ssri_model/ml/statistics_loader.py:11` | F401 | Unused `CHANNEL_COUNT` |
| 15 | `src/ssri_model/release_shell/evaluate.py:7` | F401 | Unused `collections.defaultdict` |
| 16 | `src/ssri_model/release_shell/evaluate.py:262` | F841 | Unused `maj_score` |
| 17 | `src/ssri_model/release_shell/labels_inventory.py:204` | F821 | Undefined name `Path` in annotation |
| 18 | `src/ssri_model/release_shell/routes.py:12` | F401 | Unused `fastapi.Request` |
| 19 | `src/ssri_model/release_shell/validator.py:6` | F401 | Unused `collections.defaultdict` |
| 20 | `src/ssri_model/release_shell/validator.py:34` | F401 | Unused `block5` |
| 21 | `src/ssri_model/release_shell/validator.py:37` | F401 | Unused `is_local_block_size` |
| 22 | `src/ssri_model/release_shell/validator.py:145` | F841 | Unused `dtype_notes` |
| 23 | `src/ssri_model/scripts/train_foundation_multitask.py:279` | F841 | Unused `probe` |
| 24 | `src/ssri_model/training/checkpoint.py:7` | F401 | Unused `typing.cast` |
| 25 | `tests/test_calibration.py:6` | F401 | Unused `pytest` |
| 26 | `tests/test_csv_import.py:31` | F841 | Unused `gap` |
| 27 | `tests/test_csv_import.py:87` | F841 | Unused `sample` (`if False` dead code) |
| 28 | `tests/test_hazard_factors_v2.py:5` | F401 | Unused `json` |
| 29 | `tests/test_hazard_factors_v2.py:8` | F401 | Unused `numpy` |
| 30 | `tests/test_hazard_factors_v2.py:23` | F401 | Unused `STATUS_EVALUATED` |
| 31 | `tests/test_release_shell_softmax_contract.py:5` | F401 | Unused `os` |
| 32 | `tests/test_release_shell_softmax_contract.py:8` | F401 | Unused `torch.nn.functional` |
| 33 | `tests/test_upload_row_cap.py:10` | F401 | Unused `os` |

Authoritative local capture matched CI count: **Found 33 errors.**

---

## 2. Files changed and reasons

| File | Change |
|------|--------|
| `api/app.py` | Moved all imports above `load_dotenv`; dotenv still runs before `create_app()` / `from_env()` |
| `attribution/__init__.py` | Removed unused `Any`, `Sequence` |
| `dann/train_step.py` | Removed unused `nn` import |
| `data/feature_engineering.py` | Removed unused `from_bounds` import in EE sampleRectangle helper (still used in mosaic export path) |
| `evaluation/evaluator.py` | Removed unused `cast` |
| `manual_training/validation.py` | Import only `LABEL_NODATA` |
| `ml/statistics_loader.py` | Drop unused `CHANNEL_COUNT` |
| `release_shell/evaluate.py` | Drop `defaultdict`; remove unused `maj_score` (keep `maj` for report payload) |
| `release_shell/labels_inventory.py` | Module-level `Path` import; fix F821 annotation |
| `release_shell/routes.py` | Drop unused `Request` |
| `release_shell/validator.py` | Drop unused imports; remove unused `dtype_notes` |
| `scripts/train_foundation_multitask.py` | Keep `np.load(first)` without binding (early-read side effect) |
| `training/checkpoint.py` | Drop unused `cast` |
| `tests/test_calibration.py` | Drop unused `pytest` |
| `tests/test_csv_import.py` | Remove unused `gap` / dead `sample` line |
| `tests/test_hazard_factors_v2.py` | Drop unused `json`, `numpy`, `STATUS_EVALUATED` |
| `tests/test_release_shell_softmax_contract.py` | Drop unused `os`, `F` |
| `tests/test_upload_row_cap.py` | Drop unused `os` |

**Diff size:** 18 files, ~15 insertions / ~32 deletions (lint-only).

**Not changed:** Commit C auth implementation (`auth/*`, assess/geo auth deps, `frontend/lib/api.ts`, auth tests).

---

## 3. Behavioural risks

| Area | Risk | Mitigation |
|------|------|------------|
| `app.py` dotenv order | Env not loaded before import-time readers | Confirmed imports do not read Supabase/auth env at import; `load_dotenv` still precedes `app = create_app()` |
| `maj_score` removal | Majority baseline array unused | Scalar `maj` still emitted as `majority_constant_score` |
| `probe` → bare `np.load` | Still fails early on unreadable stack | Preserved side effect without unused name |
| `Path` in labels inventory | Annotation/runtime | Top-level import; behaviour unchanged |
| Unused import removals | None | Confirmed unused via grep before delete |

No `# noqa`, no Ruff config changes, no blind `--fix`.

---

## 4. Test results

| Suite | Command | Result |
|-------|---------|--------|
| Full Ruff | `poetry run ruff check src tests` | **PASS** — All checks passed (`RUFF_FINAL=0`) |
| Focused | `pytest` csv/calibration/hazard_v2/softmax/upload_cap/manual_training/assess_auth/api_auth | **63 passed** |
| Full backend | `poetry run pytest -q --tb=line` | **828 passed, 3 skipped** (`FULL=0`) |

---

## 5. Final Ruff result

```text
All checks passed!
RUFF_FINAL=0
```

---

## 6. Remaining limitations

1. Changes are **uncommitted** (per assignment). CI on `origin/main` stays red until a follow-up commit is approved.  
2. Pre-existing client/POC leftovers remain in the working tree (`inspect_client_csv.py`, Abeokuta docs, `poc/_tmp_*`) — preserved, not cleaned.  
3. No frontend re-run required for these Python-only lint fixes (backend suite covers affected modules).

---

## 7. Preservation confirmation

| Item | Status |
|------|--------|
| Commit C `d068786` | **HEAD unchanged** |
| Commits A/B | Untouched |
| Auth implementation | **No diff** under auth/assess session paths |
| Stage / commit / push / deploy | **Not performed** |
| Phase 6 | Remains **BLOCKED** |
| 13-channel / `NOT_VALIDATED` / three hazards | Unchanged |

---

## Closing

Repository-wide Ruff is green locally against the same command CI runs. Ready for a separate owner-approved remediation commit when authorised.
