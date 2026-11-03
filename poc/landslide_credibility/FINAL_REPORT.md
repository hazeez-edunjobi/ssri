# Landslide susceptibility credibility — final report

## Phase 10 decision: **NO-GO** · Credibility level: **L1**

Built a protocol-compliant, leakage-controlled CONUS terrain-first corpus (n=1784, 20×5° blocks, min train–test NN 54.3 km) and evaluated frozen candidates once. **Slope-only already reaches test ROC-AUC 0.821.** Logistic regression and HGB do **not** beat slope with a block-bootstrap 95% CI for ΔAUC above 0 → **Tier A FAIL** for all candidates → **NO-GO**. Phase 5 layers skipped by gate; Phase 6 NASA GLC download **BLOCKED** (404). Production assess untouched; tests **93+9** unchanged. Agent cannot claim L4/L5.

---

## Results (NEAR primary, test n=309, 5 blocks)

| Candidate | ROC-AUC | PR-AUC | Brier | ECE | ΔAUC vs slope | ΔAUC 95% CI | Tier A | Tier B |
|-----------|---------|--------|-------|-----|---------------|-------------|--------|--------|
| B1 slope | **0.821** | 0.636 | 0.178 | 0.148 | 0 | [0,0] | FAIL* | FAIL |
| B2 logreg | 0.803 | 0.762 | 0.215 | 0.205 | −0.018 | [−0.085, 0.027] | FAIL | FAIL |
| B3 HGB | 0.850 | (see JSON) | (see JSON) | (see JSON) | +0.029 | [−0.070, 0.091] | FAIL | FAIL |

\*Slope is the baseline, not a “beat slope” candidate.

FAR scheme: same qualitative result (no Tier A). Disjointness tests: **2 passed**.

### Acceptance checklist (best multivariate = HGB NEAR)

| Criterion | Result |
|-----------|--------|
| Tier A: ΔAUC CI lower > 0 | **FAIL** ([−0.070, 0.091]) |
| Tier A: ≥75% blocks AUC>0.5 | PASS (see phase4 JSON) |
| Tier B: AUC≥0.80 | PASS point (0.850) but Tier A required |
| Tier B: ECE≤0.10 | FAIL |
| Plausibility PD(slope) nondecreasing | PASS (logreg) |

---

## External transfer

**BLOCKED** — NASA GLC CSV URLs returned HTTP 404 (`outputs/phase6_transfer.json`). Report-only; does not change NO-GO.

---

## Evidence ledger

| Claim | Status |
|-------|--------|
| PROTOCOL v1 hash BD2A86BC… unchanged | VERIFIED |
| PROTOCOL_v2 hash 5F63E362… at scoring | VERIFIED |
| Corpus n=1784; 12/3/5 train/val/test blocks; min NN 54.3 km | VERIFIED |
| Spectral/geophysics dropped; DEM features only | VERIFIED |
| Phase 4 metrics table | VERIFIED (`outputs/phase4_eval.json`) |
| Tier A fail all candidates | VERIFIED |
| Tests 93+9 at start/end | VERIFIED |
| NASA GLC download failed | VERIFIED |
| Live Render checkpoint identity | UNKNOWN |

---

## Owner questions

1. Accept slope-only as the honest CONUS susceptibility foil for product copy?  
2. Priority for environment layers only if a *new* holdout is reserved (current test already spent)?  
3. Approve applying softmax + landslide-only “not available” patches?

### L4 / L5 requirements (agent cannot claim)

- **L4:** Independent human scientific review using `REVIEW_CHECKLIST.md`.  
- **L5:** Prospective validation on inventory events dated after corpus freeze.

---

## Integrity statement

PROTOCOL v1 SHA-256 **BD2A86BC…** unchanged. PROTOCOL_v2 SHA-256 **5F63E362…** unchanged since commit `29c1982` before scoring. Test blocks opened once per frozen candidate after `phase3_freeze_*.json`. Existing tests **93 + 9** unchanged. No production path changed. DeepSlide not wired. No production integration authorized.
