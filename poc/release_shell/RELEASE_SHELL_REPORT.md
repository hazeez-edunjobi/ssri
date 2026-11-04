# Release shell report — blocker close-out

## Executive summary

On **`poc/release-shell`**, previous PARTIAL assess/seed/region gaps are closed behind `SSRI_RELEASE_SHELL`. Assess returns **`not_available` / `score: null`** for disabled, unlabelled, failed-gate, or unconfirmed-seed hazards; **`outside_training_region`** when the query point is outside checkpoint-stored training extent/blocks. Training jobs run **3 seeds**; **evaluated** requires the gate on **≥2 of 3**. FeatureStacks v3 (240 tiles) packaged and validated: **FAIL** on four all-sentinel channels (ndvi/ndwi/clay/iron) and hazards **DISABLED** below minimums. `scripts/verify.py` → **pass: true** (93 + 16 new tests; DeepSlide 9 SKIPPED — lives on `poc/landslide-credibility-v3`). UI is **partial** (operator classic flow + limitations); full shell flow documented in `OWNER_API_GUIDE.md`. **Nothing merged or deployed; no weights shipped.**

---

## Steps 1–9 checklist (corrected)

| Step | Status | Evidence |
|------|--------|----------|
| 1 Softmax + `no_trained_model` | **DONE** | Flag-gated; verify step `no_trained_model` → `200 no_trained_model` |
| 2 Spatial block split | **DONE** | `spatial_split.py` + tests |
| 3 DATASET_SPEC + SYNTHETIC ZIP | **DONE** | `DATASET_SPEC.md`, `templates/SYNTHETIC_stage25_template.zip` |
| 4 Upload validator | **DONE** | FeatureStacks rehearsal: channel_quality **FAIL** (4 sentinels); hazard_minimums **WARN**/DISABLED — `outputs/rehearsal/featurestacks_v3_validation.json` |
| 5 Training | **DONE** | 3 seeds per release-shell job (`job_workers._run_release_shell_multiseed_training`) |
| 6 Automatic evaluation | **DONE** | Per-seed eval + aggregate report |
| 7 Status gates | **DONE** | Single-seed gate + `aggregate_seed_gates` (≥2/3 → evaluated; else unconfirmed / no skill) |
| 8 Assess integration | **DONE** | `assess_contract.py` + checkpoint `release_shell` meta (blocks/extent/hazard gates); scores withheld unless evaluated + in-region |
| 9 Copy audit | **DONE** | `COPY_AUDIT.md` (marketing pages outside operator: UNKNOWN) |

---

## Blocker close-out (this task)

| # | Item | Status | Evidence |
|---|------|--------|----------|
| 1 | `not_available` / null score for disabled, no positives, failed gate | **DONE** | `tests/test_release_shell_assess_contract.py` (VERIFIED) |
| 2 | `outside_training_region` | **DONE** | meta extent/blocks; contract test (VERIFIED) |
| 3 | 3 seeds; evaluated iff ≥2/3 | **DONE** | `gates.aggregate_seed_gates`; job worker multi-seed (VERIFIED unit + code path) |
| 4 | `verify.py` fresh run | **DONE** | see pasted output below |
| 5 | FeatureStacks v3 rehearsal | **DONE** | ZIP + validation FAIL as required (VERIFIED) |
| 6 | UI vs endpoints | **DONE** | Partial UI; `OWNER_API_GUIDE.md` |
| 7 | Copy scan | **DONE** | `COPY_AUDIT.md` |

---

## verify.py output (actual)

```text
{
  "pass": true,
  "report": "C:\\Users\\LENOVO\\Documents\\MrBusoye\\ssri\\poc\\release_shell\\outputs\\verify_report.json"
}
```

From `outputs/verify_report.json` (VERIFIED):

- branch: `poc/release-shell`
- commit: `78e06c391008e2599bc7fd1ecfaa7ad9bfa2028d`
- new_tests: **16 passed**
- assess_93: **93 passed**
- deepslide_9: **SKIPPED** — path not on this checkout
- no_trained_model: `200 no_trained_model`

---

## FeatureStacks v3 rehearsal (VERIFIED)

- Packaged: `outputs/rehearsal/usgs_featurestacks_v3_upload.zip` (240 tiles → Stage 2.5 layout)
- Validator: **overall FAIL**, `can_train: false`
- `channel_quality` **FAIL**: ndvi, ndwi, clay_mineral_ratio, iron_oxide_index ~100% `-9999`
- `hazard_minimums`: all hazards **DISABLED** (subsidence 121 tiles / landslide 120 / sinkhole 0; default mins 300/8/3)
- Detail: `outputs/rehearsal/featurestacks_v3_validation.json`

---

## UI status

| Surface | Upload | Validate | Train | Eval report | Checkpoint select |
|---------|--------|----------|-------|-------------|-------------------|
| `/training/operator` | Classic `/training/*` | Classic preview | Classic job | No shell eval UI | Promote/active path |
| Release-shell routes | Yes | Yes | Yes (3 seeds) | Yes | Via `/training/models` + assess `checkpoint` |

Non-developers: prefer **`/shell`**, else **`OWNER_API_GUIDE.md`**.

**Superseded by consolidation:** full RC1 status lives on **`integration/ssri-shell-rc1`** — see `INTEGRATION_RC1_REPORT.md` and `CONSOLIDATION_LOG.md`.

---

## Orphan branches (resolved on integration)

| Asset | Status on `integration/ssri-shell-rc1` |
|-------|----------------------------------------|
| DeepSlide 9 | Present, unwired — `poc/landslide4sense/integration/test_deepslide_engine.py` |
| v3 slope index / PROTOCOL_v3 | Present under `poc/landslide_credibility_v3/` |
| Softmax / assess proposed patches | Kept as research archives; shell implements equivalents behind the flag |
| Archive tags | `archive/release-shell-final`, `archive/credibility-v3-final`, `archive/due-diligence-final`, `archive/ssri-shell-rc1` |

---

## Test counts (integration RC1 — VERIFIED)

| Suite | Result | Label |
|-------|------:|-------|
| Existing assess suite | 93 passed | VERIFIED |
| DeepSlide 9 | 9 passed | VERIFIED (optional `smp`+`h5py` on virgin Poetry env) |
| Release-shell tests | 21 passed | VERIFIED (16 + assess-route 4 + jobs-result 1) |
| Combined matrix flag OFF/ON | 123 passed each | VERIFIED |

---

## Hazard-by-hazard (shell)

| Hazard | Disabled if below mins | Score only if evaluated + in-region | Outside region |
|--------|------------------------|--------------------------------------|----------------|
| subsidence | yes → `not_available` | yes | `outside_training_region`, score null |
| landslide | yes | yes | same |
| sinkhole | yes (often 0 labels) | yes | same |

---

## Integrity statement

Frozen protocols v1/v2/v3 and their frozen outputs were **not edited**. Existing **93** tests pass with default flag **off**. DeepSlide remains **unwired**. **Nothing merged to main or deployed.** No production weights shipped. Claims limited to gate strings and **NOT_VALIDATED**.
