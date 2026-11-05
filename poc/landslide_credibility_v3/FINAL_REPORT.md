# Landslide susceptibility credibility v3 — FINAL REPORT

## Executive summary

**Decision: NO-GAIN · Credibility: L1**

Leave-one-block-out (LOBO) evaluation over 15 non-spent CONUS 5° blocks shows **slope-only** already ranks NEAR absences at ROC-AUC **0.891** (95% CI ≈ [0.738, 0.933]). Logistic regression and HGB do **not** beat slope under Tier A (NEAR ΔAUC CI lower ≤ 0; SLOPE-MATCHED ΔAUC point < 0). LOBO minimum detectable ΔAUC ≈ **0.06 ≤ 0.08**, so the null is **NO-GAIN** (not INCONCLUSIVE). Sealed fresh holdout under-populated (n=14, 2 blocks) → Tier B unavailable. Environment layers and NASA GLC transfer **BLOCKED** (missing files). **Shipped product = slope-only index**, labelled as such. Production `/api/v1/assess` untouched; patches proposed only.

---

## Phase 9 decision and credibility

| Field | Value |
|-------|-------|
| Decision | **NO-GAIN** |
| Credibility | **L1** — reproducible baselines on leakage-free blocks |
| Shipped index | `ssri_landslide_slope_only_v3` (DEM slope → empirical CDF ranking score) |
| Badge | `L1 — reproducible baselines on leakage-free blocks (NO-GAIN: slope-only product)` |
| L4 / L5 | Agent **cannot** claim. L4 = independent human review via `REVIEW_CHECKLIST.md`. L5 = prospective validation on post-freeze inventory events. |

---

## Complete LOBO results (ranking scores; Brier/ECE informational)

B0 majority uses a constant score → ROC-AUC is **degenerate / not interpretable** (reported as N/A). Confusion = TP/FP/FN/TN at training-selected threshold.

### NEAR (headline; n_OOF=1475; 15 both-class blocks)

| Candidate | ROC-AUC | AUC 95% CI | PR-AUC | Brier | ECE | ΔAUC vs slope | ΔAUC 95% CI | Frac blocks AUC>0.5 | Confusion |
|-----------|---------|------------|--------|-------|-----|---------------|-------------|---------------------|-----------|
| B0 majority | N/A | — | — | 0.248 | 0.000 | — | — | 0.000 | — |
| B1 slope | **0.8912** | [0.7381, 0.9327] | 0.8607 | 0.1235 | 0.0743 | 0 | [0, 0] | 0.867 | 759/187/48/481 |
| B2 logreg | 0.7217 | [0.6280, 0.8462] | 0.6515 | 0.2641 | 0.2733 | −0.1696 | [−0.2513, 0.0339] | 0.867 | 202/114/605/554 |
| B3 HGB | 0.6833 | [0.6080, 0.8555] | 0.6902 | 0.3438 | 0.3407 | −0.2079 | [−0.2797, 0.0429] | 0.667 | 357/129/450/539 |

### FAR (n_OOF=1202)

| Candidate | ROC-AUC | AUC 95% CI | PR-AUC | Brier | ECE | ΔAUC vs slope | ΔAUC 95% CI | Frac blocks AUC>0.5 | Confusion |
|-----------|---------|------------|--------|-------|-----|---------------|-------------|---------------------|-----------|
| B1 slope | **0.9038** | [0.7702, 0.9455] | 0.8989 | 0.1060 | 0.1101 | 0 | [0, 0] | 0.929 | 758/93/46/305 |
| B2 logreg | 0.7512 | [0.6567, 0.8742] | 0.7659 | 0.2203 | 0.2686 | −0.1525 | [−0.2100, 0.0139] | 0.857 | 361/84/443/314 |
| B3 HGB | 0.7925 | [0.6902, 0.8801] | 0.8762 | 0.2540 | 0.2570 | −0.1113 | [−0.1919, 0.0167] | 0.571 | 512/64/292/334 |

### SLOPE-MATCHED (beyond-slope criterion; n_OOF=1351)

| Candidate | ROC-AUC | AUC 95% CI | PR-AUC | Brier | ECE | ΔAUC vs slope | ΔAUC 95% CI | Frac blocks AUC>0.5 | Confusion |
|-----------|---------|------------|--------|-------|-----|---------------|-------------|---------------------|-----------|
| B1 slope | 0.5282 | [0.4097, 0.6398] | 0.5899 | 0.3150 | 0.2582 | 0 | [0, 0] | 0.533 | 789/470/18/74 |
| B2 logreg | 0.4137 | [0.2631, 0.6845] | 0.5081 | 0.4525 | 0.5006 | −0.1145 | [−0.3270, 0.2256] | 0.467 | 87/193/720/351 |
| B3 HGB | 0.4883 | [0.3928, 0.6878] | 0.6081 | 0.5005 | 0.5176 | −0.0399 | [−0.1865, 0.1810] | 0.267 | 269/191/538/353 |

Per-block AUCs, score histograms, and reliability inputs: `outputs/phase4_eval.json` (full numeric fields; tables above have no “see JSON” cells for headline metrics).

### Sealed fresh holdout (opened once after freeze; under-powered; n=14)

| Candidate | ROC-AUC | ΔAUC vs slope | Note |
|-----------|---------|---------------|------|
| B1 slope | 0.694 | 0 | exploratory scale only |
| B2 logreg | 0.633 | −0.061 | |
| B3 HGB | 0.592 | −0.102 | |

Does **not** meet Tier B minimum (≥3 blocks, ≥150 samples).

### Spent v2 test blocks (exploratory, second look — cannot count toward acceptance)

| Candidate | ROC-AUC | ΔAUC vs slope |
|-----------|---------|---------------|
| B1 slope | 0.821 | 0 |
| B2 logreg | 0.853 | +0.032 |
| B3 HGB | 0.866 | +0.045 |

Label: **exploratory, second look**.

---

## Acceptance checklist

| Criterion | Result |
|-----------|--------|
| Tier A NEAR: lower 95% CI of ΔAUC vs slope > 0 | **FAIL** (logreg [−0.251, 0.034]; HGB [−0.280, 0.043]) |
| Tier A SLOPE-MATCHED: ΔAUC point > 0 | **FAIL** (logreg −0.115; HGB −0.040) |
| Tier A: AUC > 0.5 in ≥75% of held-out blocks (NEAR) | PASS logreg (0.867); **FAIL** HGB (0.667) |
| Tier B sealed | **FAIL** (Tier A failed; sealed too small) |
| Partial dependence slope nondecreasing | PASS logreg (0 violations); **FAIL** HGB (4–6 violations by scheme) |
| Seeds ≥5 reported | PASS (`seed_mean_inner_auc` in phase4) |

**Outcome rule:** Tier A failed **and** LOBO MDD ≤ 0.08 → **NO-GAIN**.

---

## Power analysis

| Design | MDD ΔAUC @ power 0.8 | MDD > 0.08? |
|--------|----------------------|-------------|
| LOBO (~20 blocks × ~90) | **0.06** | No |
| Sealed (assumed 4×50) | **0.15** | Yes |

Source: `outputs/phase1_power.json` (Hanley–McNeil SE × 1.5 spatial inflation). Implication: LOBO null → NO-GAIN is protocol-allowed.

---

## Layer-by-layer ΔAUC

| Step | vs | NEAR ΔAUC point | NEAR ΔAUC 95% CI | Kept? |
|------|----|-----------------|------------------|-------|
| B1 slope | — | 0 | [0, 0] | **Yes (shipped)** |
| B2 logreg | slope | −0.170 | [−0.251, 0.034] | No |
| B3 HGB | slope | −0.208 | [−0.280, 0.043] | No |
| L1 land cover | previous best | — | — | **BLOCKED** missing raster |
| L2 precip climatology | previous best | — | — | **BLOCKED** missing raster |
| L3 lithology | previous best | — | — | **BLOCKED** missing raster |
| L4 soils | previous best | — | — | **BLOCKED** missing raster |

Details: `outputs/phase5_layers.json`.

---

## External transfer (Phase 5)

**BLOCKED.** Exact owner request: place NASA Global Landslide Catalog CSV/GeoJSON at  
`poc/landslide_credibility_v3/corpus/external/nasa_glc.csv`  
(with latitude/longitude). Do not ask the agent to guess URLs (v2 endpoints returned 404). Report-only; cannot change NO-GAIN.

---

## Failure analysis summary

Beyond-slope skill: **no**. NEAR/FAR separation is largely slope-driven (slope AUC ~0.89–0.90). After slope-matching absences, slope itself falls to ~0.53 and multivariate models remain ≤ slope. False positives tend to be steep non-inventory locations; false negatives flatter inventory points — see `outputs/phase6_failure.json` examples by block/slope/source/distance.

---

## Shipped index and copy

- **Index:** slope-only empirical CDF vs LOBO NEAR training slopes; threshold ≈ 0.40 (`phase3_freeze.json`).
- **Returns (proposed contract):** landslide ranking score only; sinkhole/subsidence `not_available` with `score: null`.
- **Framing:** relative landslide susceptibility index derived from terrain/environment; evaluated only on CONUS held-out blocks; a ranking score, not a probability and not a risk estimate; not independently reviewed.
- **Live `/api/v1/assess` today:** still Stage 2.5 multi-class assess path; **not** this index. Live Render checkpoint identity: **UNKNOWN**. Softmax/sigmoid mismatch remains (proposed patches only).
- Claims audit: `proposed_patches/CLAIMS_AUDIT.md`.

### Merge checklist (owner only — agent does not authorize production)

1. Review FINAL_REPORT + REVIEW_CHECKLIST with an independent geoscientist (L4).
2. Apply `proposed_patches/` (softmax + landslide-only) on a dedicated PR; run proposed tests then full 93+9.
3. Wire slope-only index behind an explicit non-production or clearly labelled research flag — never silent swap of checkpoint semantics.
4. Update all UX/API strings per CLAIMS_AUDIT.
5. Do **not** merge DeepSlide; do **not** claim L4/L5 without human/prospective work.

---

## Evidence ledger

| Claim | Label |
|-------|-------|
| PROTOCOL v1 SHA-256 BD2A86BC… unchanged | VERIFIED |
| PROTOCOL_v2 SHA-256 5F63E362… unchanged | VERIFIED |
| PROTOCOL_v3 SHA-256 70FE823F… frozen before scoring | VERIFIED |
| v2 corpus manifest E0D31A4F… unchanged | VERIFIED |
| LOBO NEAR B1 AUC 0.8912 | VERIFIED (`phase4_eval.json`) |
| Tier A fail → NO-GAIN with MDD 0.06 | VERIFIED |
| Sealed n=14 shortfall | VERIFIED |
| Spent blocks exploratory | VERIFIED |
| GLC / env layers missing | VERIFIED BLOCKED |
| Proposed softmax/landslide-only tests pass | VERIFIED |
| `verify.py` pass | VERIFIED (`phase8_verify.json`) |
| Existing tests 93+9 at end | VERIFIED (`phase9_tests_*.txt`) |
| Live Render checkpoint | UNKNOWN |

---

## Owner questions

1. Accept slope-only as the honest CONUS susceptibility product label under NO-GAIN?
2. Supply NASA GLC + environment rasters under `corpus/external/` if a future cycle should attempt L2/L3?
3. Approve applying proposed softmax + landslide-only patches on a separate PR?
4. Who will perform L4 review against `REVIEW_CHECKLIST.md`?

---

## Integrity statement

- PROTOCOL v1 and v2 hashes **unchanged**.
- PROTOCOL_v3 hash **unchanged** since commit before scoring (`70FE823F…`).
- Fresh holdout opened **once** per frozen candidate after `outputs/phase3_freeze.json`.
- Spent v2 blocks labelled **exploratory, second look**.
- Existing tests **93 + 9** unchanged (re-run at end: 93 passed assess suite; 9 passed deepslide isolated).
- Clean-checkout / verify: `scripts/verify.py` → `pass: true`; simple regen NEAR slope AUC 0.8876 within **0.01** of buffered headline 0.8912.
- **No production path changed. No production integration authorized.**
