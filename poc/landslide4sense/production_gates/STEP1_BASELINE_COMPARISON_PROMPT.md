# Agent prompt — Step 1: Landslide susceptibility baselines vs foundation U-Net

Copy everything below the line into a new agent chat.

---

## Objective

Run a **read-only scientific baseline comparison** on the existing USGS FeatureStacks **v3** spatial holdout to decide whether investing further in the foundation U-Net is justified versus simpler susceptibility models.

This is **not** training, not deployment, not assess wiring, and not a DeepSlide revisit. DeepSlide is out of scope.

**Product framing for this work:** landslide **susceptibility** (“terrain here is relatively prone”), not event detection. Do not claim scientific validation or production readiness.

## Hard constraints

- Do **not** modify production `/api/v1/assess`, checkpoints, preprocessing contracts, or thresholds used by any production path.
- Do **not** overwrite `models/ssri-foundation-*.pt` or FeatureStacks v3 contents.
- Prefer free/local compute only; no paid data or cloud GPU provisioning.
- Write all new scripts/outputs under `poc/landslide_susceptibility_baselines/` (create if needed).
- Label every metric claim VERIFIED (you computed it) vs REPORTED (from prior docs).

## Predeclared acceptance (write to disk BEFORE running models)

Create `poc/landslide_susceptibility_baselines/acceptance.json` first, including:

1. **Dataset:** `data/datasets/usgs_landslide_featurestacks/v3` only for this step.
2. **Split:** use existing `spatial_block_2deg` train/val/test from `manifest.json`. Primary decision uses **test**; report val as secondary. Do not reshuffle or re-split.
3. **Task:** tile-level and/or point-level **landslide susceptibility** from available channels. Prefer tile-level scores (mean/max of positive evidence) consistent with foundation eval’s tile ROC-AUC.
4. **Channels:** document which of the 13 channels are usable. Explicitly measure nodata fraction per channel on train/val/test. For model inputs in this step:
   - **Terrain-first set (required):** elevation, slope, plan_curvature, profile_curvature, twi, relative_relief, valley_depth (and gravity/magnetics if finite).
   - **Spectral:** if a channel is ≥95% nodata on the split, **exclude it** and record that; do not silently impute with zeros as “signal.”
5. **Baselines (all required):**
   - **Majority / prevalence:** always-predict-positive and always-predict-negative at the metric’s operating point; also report the F1 of always-positive given test prevalence (sanity check).
   - **Slope-only:** tile score = mean (or max—declare one) slope; threshold chosen **only on validation**, frozen for test.
   - **Simple ML:** logistic regression **and** gradient boosting (e.g. sklearn) on per-tile aggregated terrain features (mean/std/p90 of usable channels). Hyperparameters / threshold tuned **only on validation**.
   - **Foundation U-Net:** load `models/ssri-foundation-v2.pt` via existing research loader/scripts only; evaluate with the **same** tile-level protocol. Do not change the checkpoint. Document whether you use the multitask landslide head outputs as trained.
6. **Primary metrics (test):**
   - Tile ROC-AUC
   - Tile PR-AUC
   - Tile F1 / precision / recall at the **validation-chosen** threshold (or score quantile—declare)
   - Confusion counts at that threshold
   - Bootstrap 95% CIs for tile ROC-AUC and tile F1 (tile-level resample, ≥1000 replicates if compute allows; otherwise state N)
7. **Go / no-go rule (predeclare, then apply):**
   - **NO-GO for further U-Net investment (this corpus):** if foundation test tile ROC-AUC is **not** greater than slope-only **and** simple-ML best by a margin whose 95% CIs do not clearly separate (document the exact rule you froze, e.g. “U-Net AUC point estimate ≤ max(slope, simple) + 0.02” or “U-Net CI lower bound ≤ simple CI upper bound”).
   - **GO (conditional):** U-Net clearly beats both slope and simple ML on test tile ROC-AUC with non-overlapping or clearly superior CI vs the best simple method **and** beats always-positive sanity on F1 by a declared margin.
   - Either outcome is success for Step 1. Do not retrain to force GO.

Also report ECE if scores are probabilistic; if not calibrated, say so.

## Implementation notes

- Reuse existing FeatureStack sample layout (`feature_stack.npy`, labels, `spatial_block`).
- Reuse foundation inference code paths under `model/src/ssri_model/` where practical (`poetry -C model run …`).
- Do not call or patch `/api/v1/assess`.
- If foundation loading fails, stop with BLOCKED and the exact missing dependency—do not substitute DeepSlide or invent weights.

## Deliverables

1. `acceptance.json` (frozen before eval)
2. `nodata_audit.json` (per-channel nodata fractions by split)
3. `baseline_results.json` (all methods, val+test, CIs, confusion)
4. `GO_NO_GO.md` — one-page verdict: GO / NO-GO / BLOCKED, with the predeclared rule quoted and the numbers
5. Exact reproduction commands in `REPRODUCE.md`

## Out of scope (do not do)

- Retraining U-Net or simple models for production
- Fixing sigmoid/softmax on assess (note as follow-up only)
- Rebuilding the multi-thousand-sample corpus (Step 3)
- Sinkhole / subsidence
- DeepSlide
- Declaring the model scientifically validated

## Final line of the report

Return exactly one of: **GO** | **NO-GO** | **BLOCKED**, then 5–10 lines of evidence.
