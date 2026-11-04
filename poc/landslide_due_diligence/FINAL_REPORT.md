# Landslide due-diligence — final report

## Phase 9 decision: **BLOCKED**

No candidate may proceed as a susceptibility layer under this protocol. The free in-repo corpus cannot support a protocol-compliant GO (n=240 ≪ 1500; 5° train/test blocks overlap; spectral rebuild needs GEE). On the only available data, every baseline—including the foundation U-Net—**fails** predeclared acceptance (diagnostic **NO-GO**). DeepSlide remains out of scope. Production `/api/v1/assess` was not changed. Existing tests still **93 + 9 passed**.

---

## Executive summary

We froze `PROTOCOL.md` (SHA-256 `BD2A86BC…`) before any scoring. FeatureStacks v3 has **240** tiles; **ndvi/ndwi/clay/iron are 100% −9999 on every chip**; USGS CONUS catalog is CC0 with ~68% of *dated* events pre-2017 and ~79% undated. Manifest train/test remap onto **overlapping 5° blocks**, so the split is not protocol-clean. Tile-level baselines on the manifest test (n=28): slope ROC-AUC **0.694**, logistic regression **0.800**, HGB **0.772**, foundation U-Net **0.733** (identical with spectral zeroed). No method has a block-bootstrap 95% CI for ΔAUC vs slope that stays above 0. Predict-all-positive pixel F1 ≈ **0.778**, confirming pixel F1 is a weak primary. Scaling to ≥1500 repaired stacks was **stopped** (GEE spectral dependency / free-compute limits). Assess still uses sigmoid vs eval softmax (reproduced); proposed patch only. No Stage 2.5 `best.pt` in repo.

---

## Results table (manifest test, VERIFIED — `outputs/phase3_baselines.json`)

| Candidate | ROC-AUC | PR-AUC | Brier | ECE | ΔAUC vs slope (point) | ΔAUC 95% CI | PASS_ALL |
|-----------|---------|--------|-------|-----|----------------------|-------------|----------|
| B1 slope | 0.694 | 0.762 | 0.218 | 0.188 | 0 | [0, 0] | FAIL |
| B2 logreg | **0.800** | 0.857 | 0.185 | 0.189 | +0.106 | [−0.067, 0.309] | FAIL |
| B3 HGB | 0.772 | 0.847 | 0.184 | 0.215 | +0.078 | [−0.152, 0.275] | FAIL |
| B4 U-Net | 0.733 | 0.833 | 0.194 | 0.149 | +0.039 | [−0.143, 0.167] | FAIL |
| B5 U-Net spectral0 | 0.733 | 0.833 | 0.194 | 0.149 | +0.039 | [−0.143, 0.167] | FAIL |

Predict-all-positive pixel F1 reference (test masks): **0.778**.

**Sample-size caveat:** n_test=28; CIs wide; Phase 3 is diagnostic only.

### Acceptance checklist (mechanical)

| Criterion | B2 | B4 | Notes |
|-----------|----|----|-------|
| A ΔAUC CI lower > 0 | FAIL | FAIL | All candidates |
| B AUC ≥ 0.80 | PASS (B2 only) | FAIL | U-Net 0.733 |
| C ECE ≤ 0.10 | FAIL | FAIL | |
| D not near-constant | PASS | PASS | |
| E ≥75% blocks AUC>0.5 | PASS | PASS | Small both-class block count |

---

## Run log index

| Step | Artifact |
|------|----------|
| Phase 0 freeze | `outputs/phase0_freeze.json` |
| PROTOCOL | `PROTOCOL.md` (committed; hash above) |
| Phase 2 | `outputs/phase2_data_audit.json`, `DATA_AUDIT.md` |
| Phase 3 (+ retry) | `outputs/phase3_baselines.json`, `outputs/phase3_run.txt`, `outputs/run_log.txt` |
| Phase 4 stop | `outputs/phase4_scale.json` |
| Phase 5–6 skip | `outputs/phase5_freeze.json`, `outputs/phase6_final_eval.json` |
| Phase 7 | `outputs/phase7_failure_analysis.json` |
| Phase 8 | `outputs/phase8_contract_audit.json`, `proposed_patches/` |
| Tests end | 93 + 9 passed (same as Phase 0) |

---

## Evidence ledger

| Claim | Status |
|-------|--------|
| PROTOCOL hash BD2A86BC… unchanged through end | VERIFIED |
| Spectral 4 channels 100% nodata on all 240 chips | VERIFIED |
| Catalog licence CC0-1.0; dated pre-2017 frac ≈0.68; undated ≈0.79 | VERIFIED |
| Absence min distance ≥15.26 km | VERIFIED |
| 5° train∩test block overlap non-empty | VERIFIED |
| Phase 3 metrics table above | VERIFIED |
| U-Net == spectral-zeroed | VERIFIED |
| Pixel all-positive F1 ≈0.778 | VERIFIED |
| Sigmoid sum≠1 vs softmax sum=1 | VERIFIED |
| Zero Stage 2.5 best.pt/latest.pt in repo | VERIFIED |
| Tests 93+9 start and end | VERIFIED |
| GEE prevents free 1500-stack rebuild this cycle | REPORTED (prior IAM docs) + STOPPED without live 1500 build |
| Live Render assess checkpoint identity | UNKNOWN |

---

## Least costly next action

1. Owner confirms susceptibility (not detection) product language.  
2. Build a **terrain-only** (or GEE-repaired) FeatureStack corpus ≥1500 tiles with **true 5° disjoint** blocks + 20 km absence buffer under `poc/`, freeze manifest hashes.  
3. Re-run PROTOCOL Phases 5–6; expect simple logreg/HGB as primary foil; U-Net optional.  
4. Separately, owner-approved apply of `proposed_patches/SOFTMAX_CONTRACT_PATCH.md`.

---

## Questions for product owner

1. Confirm susceptibility vs detection claim for UX/API copy?  
2. Is CONUS-only OK before Africa?  
3. Approve terrain-only channel set until GEE spectral works?  
4. May assess return “not available” for sinkhole/subsidence?

---

## Integrity statement

- Test blocks for a protocol-scaled corpus were **never opened** for Phase 6 (Phase 4 stopped). Phase 3 used the pre-existing manifest test split for diagnostics only; thresholds for B1–B5 were fit on train+validation only.  
- `PROTOCOL.md` SHA-256 at end: **BD2A86BC5A883123B476F9CFD759026836740C60E09FD6A9ACE3BD088213DDFE** (unchanged since Phase 1 commit `0804ce05`).  
- Existing tests: **93 passed + 9 passed** at Phase 0 and again at end — no regression.  
- No production path, checkpoint, or deployed config was modified. DeepSlide was not wired. One invalid U-Net run (NaN scores) was logged and corrected before relying on B4/B5 numbers.
