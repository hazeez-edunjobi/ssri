# INTEGRATION RC1 REPORT — `integration/ssri-shell-rc1`

## Executive summary

All SSRI release-shell and credibility research work is consolidated on **`integration/ssri-shell-rc1`** (not merged to `main`, not deployed, no weights shipped). The owner path **upload → validate → train (3 seeds) → evaluate → assess** works behind **`SSRI_RELEASE_SHELL` (default OFF)**. SYNTHETIC end-to-end job completed with per-seed evaluation and aggregate gates. Jobs GET now exposes `progress` + `result`. Owner UI at **`/shell`**. DeepSlide remains unwired. Frozen protocol hashes unchanged. Status stays **NOT_VALIDATED**.

---

## Branch identity

| Item | Value | Label |
|------|-------|-------|
| Integration branch | `integration/ssri-shell-rc1` | VERIFIED |
| Tip at report time | `002f61add5c15882ba5315274b11a647bc125c74` (tag `archive/ssri-shell-rc1`) | VERIFIED |
| Base `main` | `9a1a44cbc9b9012e1f960a9fc9d37eb4c823e29d` | VERIFIED |
| Merged `poc/release-shell` | `35e817bc3fb5b594e63f60ffa86904e8682ed79d` / tag `archive/release-shell-final` | VERIFIED |
| Merged `poc/landslide-credibility-v3` | `374f2bd90fb2d7cfc5fff99ae7a999e6c6406b4e` / tag `archive/credibility-v3-final` | VERIFIED |
| Archived due-diligence | `6e5f1687082e491eb78d98c5f32196028a71df8a` / tag `archive/due-diligence-final` | VERIFIED |

See also `CONSOLIDATION_LOG.md` (repo root).

---

## Steps 1–6 checklist

| Step | Status | Evidence |
|------|--------|----------|
| 1 Protect work + frozen hashes | **DONE** | Branches pushed + archive tags; PROTOCOL v1/v2/v3 git-blob MATCH `BD2A86BC…` / `5F63E362…` / `70FE823F…`; v2 manifest `E0D31A4F…` MATCH (CRLF form as originally recorded) |
| 2 Consolidate | **DONE** | Merges clean (no conflicts); `CONSOLIDATION_LOG.md`; no proposed_patch removals (archives kept; shell implements equivalents) |
| 3a SYNTHETIC 3-seed job | **DONE** | `outputs/synthetic_job_final.json`, `synthetic_evaluation.json`, `synthetic_e2e_summary.json`, `acceptance_log.json` |
| 3b Assess route 4 cases | **DONE** | `tests/test_release_shell_assess_route.py` (4 tests through `/api/v1/assess`) |
| 3c Jobs GET result | **DONE** | `jobs.py` + `test_release_shell_jobs_result.py`; acceptance job_final includes `result` + `progress` |
| 3d Owner UI | **DONE** | `/shell` page: upload, validation PASS/WARN/FAIL, train progress, evaluation, checkpoint select, Known limitations. API fallback still `OWNER_API_GUIDE.md` |
| 3e Flag-off proof | **DONE** | Flag OFF suite **123 passed** (`outputs/pytest_flag_off.txt`); assess without checkpoint still 400/422 when flag off |
| 4 Tests OFF + ON | **DONE** | Both **123 passed** (`pytest_flag_off.txt`, `pytest_flag_on.txt`); breakdown below |
| 5 Clean-clone rehearsal | **DONE** | Fresh clone `ssri-rc1-rehearsal` @ `ba9330f…`; all 6 steps PASS — `outputs/rehearsal_rc1_log.json` |
| 6 Handoff docs | **DONE** | `README_OWNER.md`, `OWNER_API_GUIDE.md`, `DATASET_SPEC.md`, `LIMITATIONS.md`, `DEMO_SCRIPT.md`, `MERGE_CHECKLIST.md`, `STAKEHOLDER_SUMMARY.md` |

---

## Test results

### Flag OFF (VERIFIED)

```text
123 passed in ~19–20s
```

| Suite | Count | Notes |
|-------|------:|-------|
| Existing assess-related suite | 93 | Included in the 123 |
| DeepSlide isolated | 9 | `poc/landslide4sense/integration/test_deepslide_engine.py` |
| Release-shell | 21 | 16 prior + 4 assess-route + 1 jobs-result |

Ambient isolation: `model/tests/conftest.py` clears shell env for non-`test_release_shell*` tests so legacy behaviour stays default-off.

### Flag ON (VERIFIED)

```text
123 passed in ~18s
```

Same matrix with `SSRI_RELEASE_SHELL=true` / `SSRI_ASSESS_SOFTMAX=true` in the process environment; legacy tests still see flag off via conftest; shell tests set the flag themselves.

---

## SYNTHETIC E2E (Step 3a) — actual job log excerpt (VERIFIED)

From `outputs/synthetic_e2e_summary.json` / `synthetic_job_final.json`:

- Job `job-b57c1cf767cc9ab4` → **completed**
- Seeds **42, 43, 44**
- Progress phase: `evaluated`
- Message: trained 3 seeds; held-out evaluation complete; **NOT_VALIDATED**
- Aggregate hazard gates (SYNTHETIC): all three → `trained, no demonstrated skill beyond slope` (seeds_passed: 0)
- Per-seed AUC / ΔAUC vs slope recorded in `synthetic_evaluation.json` (fabricated data — do not treat as real skill)

Jobs GET now returns `result` and `progress` in one payload (VERIFIED in acceptance log).

---

## Clean-clone rehearsal log (VERIFIED)

Clone dir: `C:\Users\LENOVO\Documents\MrBusoye\ssri-rc1-rehearsal`  
Commit: `ba9330fd6dcafb35509754ea3113290d3cc47330`  
Log: `poc/release_shell/outputs/rehearsal_rc1_log.json`

| # | Step | Expected | Result |
|---|------|----------|--------|
| 0a | Fresh clone + `poetry install` | ok | DONE |
| 0b | `scripts/verify.py` | pass | **PARTIAL** — assess 93 + shell 21 + no_trained_model PASS; DeepSlide initially 5 ERROR / later 1 FAIL until optional `pip install segmentation_models_pytorch h5py` (not in poetry.lock). After optional deps: **9 passed**. Recorded as open risk for virgin envs. |
| 1 | assess no checkpoint | `no_trained_model` | PASS (200) |
| 2 | broken ZIP | FAIL, train refuses | PASS (overall FAIL, train 400) |
| 3 | FeatureStacks v3 ZIP | FAIL on 4 sentinels; hazards DISABLED | PASS (channel_quality FAIL on ndvi/ndwi/clay/iron; all 3 hazards DISABLED). ZIP copied from developer machine because gitignored. |
| 4 | SYNTHETIC → train 3 seeds → eval → gates | PASS/WARN → completed | PASS (WARN, can_train true, seeds 42/43/44, job completed, result present) |
| 5 | select ckpt → assess | scores or not_available + hashes/limitations | PASS — all hazards `not_available` / score null (gate: no demonstrated skill beyond slope on SYNTHETIC); checkpoint hash present |
| 6 | outside region | `outside_training_region` | PASS (3/3 hazards, score null) |

---

## Hazard-by-hazard (shell today)

| Hazard | Validation disable | Score only if evaluated + in-region | Outside region |
|--------|--------------------|--------------------------------------|----------------|
| subsidence | yes if below mins | yes | `outside_training_region`, score null |
| landslide | yes | yes | same |
| sinkhole | yes (often 0 labels) | yes | same |

---

## Open risks

- FeatureStacks v3 as-shipped cannot train until four spectral channels are repaired (VERIFIED rehearsal FAIL).
- SYNTHETIC gates will usually be “no demonstrated skill beyond slope” — expected on tiny fake data.
- `/shell` UI depends on API env flag; if flag off, page tells operator to enable it.
- Large `poc/landslide4sense` binaries inflate clone size (GitHub warned on ValidData.zip).
- DeepSlide 9 on a virgin Poetry env needs optional `segmentation_models_pytorch` + `h5py` (not declared in `model` poetry deps) — VERIFIED blocker until installed; engine remains unwired.
- FeatureStacks rehearsal ZIP is gitignored; clean-clone step 3 needs the ZIP present locally or uses prior validation JSON.

## Owner decisions

1. When to merge `integration/ssri-shell-rc1` → staging → main (see `MERGE_CHECKLIST.md`).
2. Whether to lower production minimums for first real upload or keep 300/8/3.
3. Whether to keep DeepSlide forever unwired or plan a separate loader (out of scope for RC1).

---

## Integrity statement

- Frozen hashes for PROTOCOL v1/v2/v3 **unchanged** (git blob VERIFIED).
- **Nothing merged into `main`.**
- **Nothing deployed.**
- **No production weights shipped.**
- Default behaviour with `SSRI_RELEASE_SHELL` unset/false **unchanged** (VERIFIED by flag-OFF suite + legacy assess expectations).
- DeepSlide **unwired** (no API/production model imports).
- Claims limited to gate strings and **NOT_VALIDATED** — no risk, probability, detection, calibration, or validation wording.
