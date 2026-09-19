# SSRI Scientific Validation Report

**Status:** INCOMPLETE — PRD gates not met  
**Date:** 2026-09-09

## Baseline preserved

| Experiment | Dataset | Test tile ROC-AUC | Notes |
|------------|---------|-------------------|-------|
| `20260909T001911Z` | v2 n=80 | **0.574** | Honest pilot baseline — **not overwritten** |
| `20260909T025912Z` | v3 n=240 | **0.750** | Expanded + audited sampling |

## Latest source holdout (`20260909T025912Z`)

**Checkpoint:** `models/ssri-foundation-v2.pt`  
**Split:** spatial 2° blocks — train 179 / val 33 / test 28

| Metric | Target | Actual (test) |
|--------|--------|----------------|
| Tile ROC-AUC | ≥ 0.88 | **0.750** |
| Tile PR-AUC | — | **0.815** |
| Pixel ROC-AUC | — | **0.732** |
| Pixel precision | — | **0.768** |
| Pixel recall | — | **0.876** |
| Pixel F1 | — | **0.818** |
| Tile Brier | — | **0.178** |
| Pixel Brier | — | **0.185** |
| ECE (10 bins) | ≤ 0.08 | **0.094** |

**Gates:** `source_auc_gate_passed = false`

### Sampling validity (not AUC-optimized)

- Pseudo-absences: full CONUS inventory 15 km buffer; **0** violations in audit
- Spatial split: **0** multi-split blocks; min train–test NN **17.1 km**
- See `docs/SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md`, `docs/SOURCE_SPATIAL_SPLIT_AUDIT.md`

## EIGEN-6C4

Interface + acquisition doc shipped. **No EIGEN-6C4 raster on disk.** FeatureStacks remain **WGM2012** with explicit labels.

## African / Phase 3

| Candidate | Usable now? |
|-----------|-------------|
| UGLC Nigeria/Africa | **Best candidate** — Zenodo download failed (504); manual CSV needed |
| Lagos InSAR | BENCHMARK-ONLY (not landslide GT) |
| NEMA | Needs human portal export |
| NGSA maps | Not event labels |
| COOLR | Sparse / FeatureServer blocked |

**Phase 3 direct transfer:** **BLOCKED** until labelled African points are on disk.

## Honest claim boundary

Larger real USGS FeatureStacks improved measured source AUC from 0.574 → **0.750**.
This does **not** meet PRD ≥0.88 and does **not** validate Geological Domain Adaptation.
