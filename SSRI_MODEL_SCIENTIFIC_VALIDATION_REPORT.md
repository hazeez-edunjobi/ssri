# SSRI — Model Scientific Validation Report

**Date:** 2026-11-21  
**Status:** Phase 6 / schema-v2 production promotion — **BLOCKED**  
**Production contract:** Stage 2.5, **13 channels**, three hazards (subsidence, landslide, sinkhole)  

---

## Verdict

**No scientifically evaluated schema-v2 production checkpoint exists in this repository.**  
Live 16-channel inference must **not** be activated.

This report records the acceptance gate and current evidence — it does **not** invent metrics.

---

## Production model contract (v1)

| Item | Evidence |
|------|----------|
| Architecture | `SSRIModel` / `SSRIModelConfig.in_channels = CHANNEL_COUNT` |
| Channels | 13 — `ml/constants.py` `CHANNEL_NAMES` |
| Safety | `inference/safety.py` rejects mismatched `in_channels` / statistics |
| Hazards | `LabelClass`: subsidence, landslide, sinkhole |
| Scientific status | Operators must treat outputs as **NOT_VALIDATED** susceptibility aids |

In-repo `.pt` files: **none** (cannot cite a git-tracked production weight hash here).

---

## Schema v2

| Item | Status |
|------|--------|
| Channel order (16) | Defined in `release_shell/channel_schema.py` `CHANNEL_NAMES_V2` |
| Offline stack expansion | Geological / `feature_apply` can produce 16-ch `.npy` |
| Training for v2 production | No evidenced completed campaign with spatial holdout + baselines |
| Checkpoint metadata tying schema | Not found as production artifact |
| Live assess path using catalogue | **Not wired** (correct) |

---

## Acceptance gate (must all pass before Phase 5/6)

| # | Requirement | Current |
|---|-------------|---------|
| 1 | Schema matches checkpoint metadata exactly | Fail — no v2 prod checkpoint |
| 2 | Checkpoint metadata complete | Fail |
| 3 | Training provenance reproducible | Fail / unknown |
| 4 | Evaluation split defensible (spatial leakage controlled) | Not evidenced for v2 |
| 5 | Baselines documented (13-ch, terrain-only, etc.) | Not evidenced for v2 |
| 6 | Uncertainty / confidence evaluated | Not evidenced for v2 |
| 7 | Inference safety tests for versioned path | v1 safety only |
| 8 | Per-hazard behaviour assessed | Incomplete for v2 |
| 9 | Limitations documented | This report + scorecard |

Historical scorecard (`docs/SSRI_COMPLETION_SCORECARD.md`): source AUC/ECE gates **failed** or incomplete — do not treat foundation research as production validation.

---

## Required next scientific work (no shortcuts)

1. Confirm geological inputs (see `SSRI_SCIENTIFIC_DATA_READINESS_REPORT.md`).  
2. Build labelled, CRS-consistent Stage 2.5 datasets with spatial CV.  
3. Train schema-v2 with fixed seed, logged config, channel schema id in checkpoint.  
4. Compare to 13-ch and simpler baselines using PR-AUC/F1/calibration **per hazard**.  
5. Only then design a **versioned** inference path with rollback to v1.

Until then: **`scientific_validation_status` remains NOT_VALIDATED**; Phase 6 remains **BLOCKED**.
