# SSRI — Non-Synthetic Stage 2.5 Model Training & Registry Preparation

**Date:** 2026-11-21  
**Mode:** Dataset audit + quality gates; **training stopped before execution**  
**Baseline:** `ssri-completed` / HEAD `d4a4a12`  
**Critical rule observed:** do not fabricate labels; do not train or promote on synthetic/unverified weights  

---

## Executive decision

```text
SUITABILITY: NOT READY FOR GENUINE STAGE 2.5 TRAINING
ACTION TAKEN: STOPPED BEFORE TRAINING
REGISTRATION: NOT PERFORMED
ACTIVATION: NOT PERFORMED
SCIENTIFIC STATUS: REMAINS NOT_VALIDATED
```

Real 13-channel feature stacks exist (USGS FeatureStacks v3). A scientifically defensible **three-class** Stage 2.5 labelled package (subsidence=0, landslide=1, sinkhole=2) with non-leaky train/validation splits **does not exist on disk**. Therefore training, evaluation, registration and activation were **not** started.

---

## 1. Dataset audit and provenance

### 1.1 Stage 2.5 production contract (requirements)

| Requirement | Source |
|-------------|--------|
| Model | `SSRIModel` (`architecture/model.py`), `in_channels=13`, `num_classes=3` |
| Channels | `CHANNEL_NAMES` order in `ml/constants.py` |
| Labels | `LabelClass`: subsidence (0), landslide (1), sinkhole (2); nodata `-1` |
| Layout | `{dataset}/manifest.json`, `statistics.json`, non-empty `train/` **and** `validation/` with `feature_stack.npy` `(13,H,W)`, `label.tif`, `metadata.json` |
| Loader | `SSRIDataset` + `write_manifest` — do not invent a second schema |
| Checkpoints | `best.pt` with `model_state_dict` + `model_config` |
| Registry | Auto-register via `ModelRegistry.register_from_training`; promote only via `POST /api/v1/training/models/activate` |

Training entry: `POST /api/v1/training/jobs` → `run_manual_training` → `Trainer.fit` (no alternate architecture).

### 1.2 Inventory (this session + readiness audit)

| Dataset | Provenance | Geography | Channels | Labels | Classification | Stage 2.5 ready? |
|---------|------------|-----------|----------|--------|----------------|------------------|
| USGS FeatureStacks **v3** | USGS US Landslide Inventories v3 (ScienceBase DOI `10.5066/P14AJF8I`) + GEE DEM/spectral + WGM2012/EMAG2 | CONUS | **13** exact `CHANNEL_NAMES`; sample shape e.g. `(13, 68, 58)` | Binary landslide / pseudo-absence; **subsidence & sinkhole missing** | `REAL_PARTIALLY_VERIFIED` | **No** |
| USGS FeatureStacks v1/v2 | Same family | CONUS | 13 | Same binary semantics | `REAL_PARTIALLY_VERIFIED` | **No** |
| USGS catalog v3 | Inventory points/polygons | CONUS | N/A | Landslide presence only | `REAL_VERIFIED` (inventory) | Label **source** only |
| WGM2012 + EMAG2v3 | BGI / NOAA | Global + CONUS/Lagos clips | gravity, magnetics | Unlabelled | `REAL_VERIFIED` (features) | Inputs only |
| `SYNTHETIC-300k` / shell templates | Generated rehearsal | Synthetic | 13 or 16 | Synthetic three-class | `SYNTHETIC` | **Forbidden** for production |
| `featurestacks_v3_stage25` package | Repackaged USGS v3 | CONUS | 13 | Declares three-class; **still binary semantics**; val = 1 leaky copy | `FIXTURE_OR_REHEARSAL` | **No** |
| UGLC Africa / Lagos InSAR / Florida FGS / NASA COOLR | Documented candidates | Africa / Lagos / FL / global | — | **Not on disk** as Stage 2.5 packages | Absent | **Blocked** |
| `handover` checkpoint | Local tiny Stage 2.5 weights | — | 13 | Not a dataset | Unverified weights | **Not** production-grade |

**Verified this session:** `data/datasets/usgs_landslide_featurestacks/v3` has **240** sample directories; representative `feature_stack.npy` is `(13, 68, 58)` with documented `FEATURE_NODATA=-9999` coverage; packaged Stage 2.5 tree has `train=240`, `validation=1`.

### 1.3 USGS v3 label semantics (authoritative)

From `data/datasets/usgs_landslide_featurestacks/v3/manifest.json` → `label_semantics`:

- Landslide: binary inventory / pseudo-absence pilot  
- Subsidence: **missing** (nodata / mask=0)  
- Sinkhole: not a Stage 2.5 three-class target in this package  

Feeding binary `label.tif` values `{0,1}` into Stage 2.5 would map `0→subsidence` and `1→landslide` — **semantic corruption**, not scientific training.

Pseudo-absences are explicitly **not** field-confirmed absences.

---

## 2. Dataset suitability decision

| Gate | Result |
|------|--------|
| All 13 channels present & ordered | **Pass** (USGS v3 features) |
| Feature normalization / NoData documented | **Pass** (partial; nodata fraction non-trivial) |
| Labels match Stage 2.5 three-class target | **Fail** |
| Non-empty independent validation without leakage | **Fail** (repackaged tree uses 1 duplicate val tile; native v3 is not `SSRIDataset` layout) |
| No synthetic contamination of production eval set | **Fail** if SYNTHETIC trees used; USGS alone insufficient for three hazards |
| Provenance recorded | **Pass** for USGS inventory + geophysics |

**Decision: STOP.** Do not train. Do not register. Do not activate.

`SYNTHETIC-300k` and `handover` remain disqualified regardless of channel compatibility.

---

## 3. Feature and label compatibility

| Hazard | Feature stacks | Stage 2.5 raster GT on disk | Compatibility |
|--------|----------------|-----------------------------|---------------|
| Landslide | Yes (USGS v3) | Binary presence / pseudo-absence only | **Partial** — binary pilot possible under a **different** contract; not current Stage 2.5 three-class |
| Subsidence | Same stacks could host labels | **None** | **Incompatible** |
| Sinkhole | Same | **None** | **Incompatible** |

---

## 4–8. Training, evaluation, checkpoint, registry

| Step | Status |
|------|--------|
| 4. Training configuration | **Not started** |
| 5. Training results | **N/A** |
| 6. Independent evaluation / baselines | **N/A** |
| 7. Baseline comparison | **N/A** |
| 8. Checkpoint artifact | **None produced** |
| 9. Registry registration | **Not performed** |
| 10. Activation readiness | **Not ready** — `active.json` still requires a future genuine promote |

No fabricated metrics. No silent synthetic substitution.

---

## 9. Activation readiness (current)

| Check | Status |
|-------|--------|
| Non-synthetic Stage 2.5 candidate registered | **No** |
| `POST /api/v1/training/models/activate` candidate | **None** |
| `GET /api/v1/ready` → `model_registry.checkpoint_available` | Expected **false** until a real promote |
| Genuine authenticated production assess | **Blocked** by missing promoted checkpoint |

---

## 10. Remaining scientific validation requirements

Even after a future genuine train + register + **explicit** activate:

- Status must remain **`NOT_VALIDATED`** until independent scientific validation evidence exists.  
- API success ≠ scientific validity.  
- Geographic generalization (especially Nigeria / Africa AOIs) requires labelled holdouts outside CONUS training geography.

---

## Precise data acquisition and labelling plan

### Goal

Produce one Stage 2.5 package that passes `validate_training_dataset` and supports honest three-class training **without** inventing geology.

### Phase A — Decide product labelling strategy (required before collection)

**Option A1 (recommended for honesty):** keep live assess as **three-class**, acquire real labels for **all three** hazards in the same spatial scheme.  
**Option A2 (narrower science):** train a **landslide-only** research model under a separate contract — **must not** be promoted into current Stage 2.5 assess without a new loader and product decision (would be a contract change).

This plan assumes **Option A1** unless product owners explicitly change the live contract.

### Phase B — Acquire authoritative inventories

| Hazard | Preferred sources (examples; license + ethics review required) | Acceptance criteria |
|--------|------------------------------------------------------------------|---------------------|
| Landslide | USGS US Landslide Inventories (already on disk); UGLC Africa / national geological surveys for Nigeria holdout | Documented DOI/license; geometry CRS; event vs susceptibility semantics recorded |
| Subsidence | Peer-reviewed InSAR VLM / government subsidence maps for target regions (e.g. Lagos candidates already documented in `docs/`) | Thresholded / classified GT with method note; not raw LOS alone without labelling policy |
| Sinkhole | State/national sinkhole incident inventories (e.g. FGS-class datasets where licensed) | Point/polygon with date, confidence; false-positive review |

**Do not** use pseudo-absence as “verified negative” without documenting uncertainty and separate evaluation protocols.

### Phase C — Build FeatureStacks on the Stage 2.5 contract

1. For each labelled AOI tile, build `(13, H, W)` stacks using existing FeatureStack / USGS builder patterns (`ssri_model.scripts.build_usgs_feature_dataset` and geophysics loaders).  
2. Preserve `CHANNEL_NAMES` order; `FEATURE_NODATA=-9999`.  
3. Write mutual-exclusive `label.tif` with values `{0,1,2}` and `-1` nodata — **never** remap binary `{0,1}` into three-class without an explicit, reviewed encoding policy.  
4. Emit `train/` / `validation/` / optional `test/` via `write_manifest` + `statistics.json`.  
5. Use **spatial-block** or geographically separated splits (prefer over random ID shuffle) and record the split policy in the manifest.

### Phase D — Quality gates (must all pass)

- [ ] 13 channels present & ordered  
- [ ] Non-empty train **and** validation; **zero** sample-id leakage  
- [ ] Class histogram reported; no silent all-background tiles without rationale  
- [ ] No `SYNTHETIC*` samples in the production evaluation split  
- [ ] Provenance JSON (source DOI, acquisition window, CRS, resolution, licence)  
- [ ] `validate_training_dataset` succeeds  

### Phase E — Train / evaluate / register (only after Phase D)

1. `POST /api/v1/training/datasets` → `register-path` or zip upload.  
2. `POST /api/v1/training/jobs` with recorded seeds and config.  
3. Independent eval on held-out real tiles: precision, recall, F1, PR-AUC, ROC-AUC where defined, confusion matrix, geographic slices, calibration if available.  
4. Compare to simple baselines (e.g. slope-only / majority class) — required in the evaluation report.  
5. `register_from_training` (automatic) — **do not** call activate.  
6. Human approval gate → `POST /api/v1/training/models/activate`.  
7. Verify `GET /api/v1/ready` `model_registry.checkpoint_available=true` and authenticated assess on deployed API.  
8. Keep `scientific_validation_status=NOT_VALIDATED` until scientific review signs off.

### Phase F — Minimum viable Nigeria / client geography

For client AOIs (e.g. Abeokuta / Lagos):

- CONUS-only USGS landslide stacks **do not** establish African generalization.  
- Plan a labelled African holdout (UGLC or national inventory) **before** claiming regional skill.  
- Geological conditioning (lineaments / overburden) remains separate from hazard GT and must not be sold as live 13-channel score drivers until evaluated.

---

## Bottom line

```text
REAL 13-CHANNEL FEATURES: AVAILABLE (USGS v3)
REAL THREE-CLASS STAGE 2.5 LABELS: NOT AVAILABLE
TRAINING: STOPPED
PROMOTION: FORBIDDEN UNTIL A GENUINE CANDIDATE EXISTS
NEXT STEP: EXECUTE DATA ACQUISITION & LABELLING PLAN (PHASES A–D)
```

A genuine but unvalidated future candidate is preferable to any synthetic “production-ready” model. No synthetic or handover weights were trained, registered or activated in this task.
