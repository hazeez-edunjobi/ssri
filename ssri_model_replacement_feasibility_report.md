# SSRI — Existing AI Model Replacement Feasibility and Working Prediction Plan

**Date:** 2026-11-03  
**Scope:** Read-only audit and feasibility study. No code changes, installs, retraining, deployment, or paid API calls.  
**Related reports:** `docs/ai_model_selection_discovery.md`, `ssri_free_first_ai_model_audit.md`, `docs/SCIENTIFIC_VALIDATION_REPORT.md`, `docs/HAZARD_TAXONOMY.md`

**scientific_status:** NOT_VALIDATED

---

## Executive conclusion

**Recommendation: BLOCKED BY DATA**

The least stressful path is **not** further tinkering with the current weights or swapping in a foundation EO model. The product requires three ground hazards with spatially explicit susceptibility; the available labelled corpus does **not** support training or validating that three-class engine. Existing pretrained EO models do not accept SSRI’s 13-channel contract and do not ship validated sinkhole/subsidence heads.

**Preferred near-term engineering candidate (after labels exist):** keep the lightweight Stage 2.5 `SSRIModel` U-Net (~2.25M params, CPU-friendly) and **retrain** it on a properly labelled Stage 2.5 dataset — or temporarily narrow the product to **landslide-only** with honest taxonomy if only landslide inventories can be obtained first.

**Software repair alone** (CORS, API keys, softmax) can make the API *run*, but cannot create missing hazard labels or fill all-nodata spectral channels. Do not spend primary effort on REPAIR expecting “dependable predictions.”

---

## 1. What SSRI must actually do vs what exists

| Requirement | Status | Notes |
|-------------|--------|-------|
| Assess subsidence susceptibility | **Aspirational / unimplemented scientifically** | Class index exists in `SSRIModel`; no verified labelled Stage 2.5 corpus for subsidence in-repo |
| Assess landslide susceptibility | **Partial** | USGS landslide FeatureStacks v3 + foundation pilot; gates unmet (AUC 0.750 &lt; 0.88) |
| Assess sinkhole susceptibility | **Aspirational / unimplemented scientifically** | Live assess vocabulary uses sinkhole; PRD multitask uses liquefaction instead (`docs/HAZARD_TAXONOMY.md`) — different phenomena |
| Spatially explicit outputs | **Implemented (software)** | Runner writes class/probability/confidence GeoTIFFs |
| Geographic alignment / CRS | **Implemented (software)** | FeatureStack / rasterio pipelines; CSV requires CRS |
| Uncertainty | **Incomplete** | Default `dropout=0.0`; MC variance not stochastic |
| Scientific limitations disclosed | **Implemented (copy)** | NOT_VALIDATED messaging; demo/fixture paths exist |
| Natural-language explanation | **Implemented (templates)** | Not a substitute for prediction |

**Do not confuse** template/LLM explanations with valid geospatial prediction.

---

## 2. Why the current model is not producing dependable results

### Confirmed root causes (repository + disk evidence)

| Cause | Evidence | Impact |
|-------|----------|--------|
| **No Stage 2.5 assessable checkpoint on disk** | `models/` contains only `ssri-foundation-v1.pt` and `ssri-foundation-v2.pt` (~9.2 MB each). Glob finds no `best.pt` / Stage 2.5 assess payload | Production assess cannot load a genuine three-class Stage 2.5 weight from this workspace |
| **Foundation checkpoints incompatible with assess loader** | v2 keys: `state_dict`, `config`, … — **no** `model_state_dict` / `model_config` (required by `evaluation/evaluator.py` / `load_inference_checkpoint`) | Assess loader rejects foundation files |
| **Training data is landslide inventory, not three-class hazards** | Dataset path `usgs_landslide_featurestacks/v3`; taxonomy doc: landslide inventories leave other hazards missing; foundation uses masked multitask BCE | Cannot honestly train sinkhole/subsidence as supervised classes from this set |
| **Spectral channels empty** | Sample stack `(13, H, W)`: channels 7–10 (ndvi, ndwi, clay_mineral_ratio, iron_oxide_index) **100% FEATURE_NODATA (−9999)** in probed sample; prior full-scan audit reported all 240 stacks | Model cannot use spectral predictors; statistics treat those channels as constant nodata |
| **Scientific gates failed** | `docs/SCIENTIFIC_VALIDATION_REPORT.md`: test tile AUC **0.750** (need ≥0.88), ECE **0.094** (need ≤0.08) | Even landslide pilot is below PRD quality bars |
| **African / multi-hazard GT blocked** | `docs/AFRICAN_TARGET_DATA_STATUS.md`: UGLC download blocked; Lagos InSAR benchmark-only; Phase 3 blocked | No validated target-domain labels |
| **Probability contract inconsistency** | Assess / MC path: `torch.sigmoid`; runner: softmax (`assess.py`, `uncertainty/__init__.py`, `predictions.py`) — re-verified 2026-11-03 | Even successful HTTP responses may not be mutually exclusive class probabilities |
| **Deployed end-to-end prediction unverified** | Prior authenticated production self-test **BLOCKED** (no API key); browser CORS blocked `ssri-gamma.vercel.app` | Dependable live prediction not demonstrated |

### Hypotheses (plausible, not fully re-proven this session)

| Hypothesis | Why plausible |
|------------|---------------|
| Full-suite flaky training poll | Prior intermittent test; not the primary prediction failure |
| Live acquisition off / geophysics incomplete | Defaults `SSRI_LIVE_ACQUISITION_ENABLED=false`; EIGEN-6C4 raster missing |
| Fixture/demo used in past Lagos qualify | `docs/production_qualification.md` — engineering fixture, not science |

### What is *not* the primary failure

- Missing FastAPI / frontend scaffolding (they exist).
- Need for a giant LLM to “replace” rasters (LLMs do not produce defensible susceptibility maps).
- Parameter count of `SSRIModel` (~2.25M) being “too small” — architecture is adequate for a CPU research model **if** labels and features are sound.

**Passing unit tests ≠ predictive value.** Suite verifies software contracts; scientific gates failed separately.

---

## 3. Current model and data readiness

### Model

| Item | Fact |
|------|------|
| Assess architecture | `SSRIModel` U-Net, 13→3 classes, dropout 0 |
| Research architecture | `SSRIMultiTaskModel` heads: landslide, subsidence, **liquefaction** |
| Loadable by `/api/v1/assess` today from this disk | **No verified Stage 2.5 checkpoint** |
| Foundation v1/v2 | Multitask research; wrong payload keys for assess |

### Data (USGS v3 FeatureStacks)

| Item | Fact |
|------|------|
| Samples | 240 (train 179 / val 33 / test 28) |
| Channels | 13 arrays present |
| Spectral 7–10 | All-nodata in probed stack (and prior full audit) |
| Labels | Landslide presence / pseudo-absence programme — **not** three-class sinkhole+subsidence maps |
| Geographic | CONUS source pilot |

### Minimum dataset requirements before a defensible three-class model

1. **Per-hazard inventories** with documented definitions for subsidence, landslide, and sinkhole (or explicitly drop a class).
2. **Aligned FeatureStacks** with populated channels (or documented omission of empty channels and model redesign).
3. **Non-empty train and validation** spatial splits with leakage checks.
4. **Held-out test** spatially separated; African/target set if that is the product geography.
5. **Never** treat missing hazard annotations as true negatives for other classes (taxonomy already warns; foundation used masking — Stage 2.5 softmax CE cannot invent missing classes).

Until then, any “working demo” is software theatre or single-hazard research — label it honestly.

---

## 4. Alternative pretrained models

| Candidate | Inputs | SSRI 13-ch? | Hazards | Weights / code | Fine-tune needed? | Spatial outputs? | License | SSRI fit |
|-----------|--------|-------------|---------|----------------|-------------------|------------------|---------|----------|
| **Prithvi-EO-2.0** | HLS 6-band | No — transform would drop gravity/magnetics/terrain stack semantics | Land cover / flood / burn examples; landslide fine-tunes exist in workshops | HF Apache-2.0 | Yes for any hazard | Yes (seg heads) | Apache-2.0 | **Not drop-in**; research encoder only |
| **Clay v1.5** | Multi-sensor EO | No | Embeddings / fine-tune tasks | Apache-2.0 (pin version) | Yes | Via fine-tuned heads | Apache-2.0 | Same |
| **Landslide4Sense baselines** | 14-band contest chips | Different band set | **Landslide detection** only | Public baseline + pretrained U-Net for contest | Domain shift to SSRI AOIs | Yes | Check contest/repo terms | Useful **landslide-only** PoC reference, not sinkhole/subsidence |
| **Pacitan LSM benchmark** | 11 controlling-factor rasters | Partial terrain overlap; not SSRI stack | Landslide susceptibility | Public rasters/points (Mendeley) | Train from scratch/classical ML | Yes | Check dataset license | Data for landslide susceptibility experiments |
| **Hosted LLM APIs** | Text | N/A | None | Free tiers exist | N/A | **No** | Provider ToS | Explanations only (`AUGMENT` in free-first audit) |

**No candidate predicts SSRI’s three hazards out of the box with matching inputs and published evidence.** Claiming otherwise would invent capabilities.

---

## 5. Comparison of practical alternatives

| Option | Effort | Free / paid | Hardware | Data need | Scientific risk | API/FE fit | Spatial hazards? | Evidence before prod |
|--------|--------|-------------|----------|-----------|-----------------|------------|------------------|----------------------|
| **A. Repair current** | Low–med (softmax, CORS, key, promote ckpt) | Free | Existing CPU | Does **not** create labels | High if claimed “fixed predictions” | High | Only if a real Stage 2.5 ckpt + data exist | Software E2E + science gates |
| **B. Replace w/ pretrained EO** | High | Weights often free; GPU may cost | Often GPU | Still need labels for heads | High modality mismatch | Medium (new loader) | After fine-tune | Spatial CV vs inventories |
| **C. Fine-tune pretrained** | High | Free weights + compute | GPU preferred | Labelled hazard maps matching bands | Medium if landslide-only; high if force 3-class | Medium | Yes if trained properly | Beats baseline on held-out spatial blocks |
| **D. Retrain simple geospatial model** | Med | Free local torch | CPU OK for U-Net size | **Blocking** — need real labels | Lowest *if* data OK | Highest (same Stage 2.5 contract) | Yes | Metrics + map QA |
| **E. Hosted AI API** | Low for text | Free quotas / paid | None | N/A for maps | Critical if used as scores | Easy for text | **No** for rasters | N/A for prediction |

---

## 6. Decisive proof of concept (smallest honest experiment)

### If product stays three-class (subsidence / landslide / sinkhole)

**PoC cannot succeed with current data.** First deliverable is a **labelled Stage 2.5 pilot** (even small):

1. ≥N tiles with verified labels for **all three** classes (or explicit nodata, never fake negatives).
2. All 13 channels populated or channels dropped with config change.
3. Spatial train/val split; held-out block.
4. Train `SSRIModel` from scratch; softmax outputs; map overlay.
5. Baseline: majority class / slope-only logistic.
6. **Pass:** beats baseline on held-out spatial metrics; maps change under feature perturbation; no empty spectral channels used as signal.
7. **Fail:** any class without positives; nodata masquerading as features; AUC/F1 not above baseline.

### If product temporarily scopes to **landslide-only** (honest renaming)

1. Use USGS v3 **after** fixing spectral acquisition **or** train on terrain+gravity+magnetics only with documented channel subset.
2. Or adopt Landslide4Sense / Pacitan as external benchmark (license review).
3. Binary or single-head susceptibility; **do not** emit sinkhole/subsidence scores.
4. Acceptance: spatial holdout beats baseline; publish NOT_VALIDATED; no three-class UI claims.

### Forbidden success criteria

- Demo mode / fixture checkpoint / hardcoded Lagos scores.
- LLM prose without rasters.
- Softmax/sigmoid “fix” without a real checkpoint and labels.

---

## 7. Reusable vs replaceable components

### Keep

- FastAPI app, `/api/v1/assess` and `/api/v1/inference` shapes (adapt only contracts that are wrong).
- Auth (API key + Supabase platform) — do not redesign.
- Manual Training ZIP/CSV → Stage 2.5 ingest/validation.
- JobService / Celery / LocalJobExecutor.
- Raster I/O, FeatureStack pipeline (fix acquisition quality).
- Frontend dashboard / training UI.
- Deploy targets (Vercel / Render / Railway).

### Replace or rebuild

- **Weights and labels** (primary).
- Assess probability transform (sigmoid → softmax for mutually exclusive Stage 2.5).
- Possibly channel set if spectral remains unavailable.
- Hazard vocabulary consistency (sinkhole vs liquefaction) — product decision, not silent rename.

### Do not rebuild

- Auth portal, new queue, new framework, admin portal.

---

## 8. Free vs paid options

| Approach | Free aspect | Paid / cost risk |
|----------|-------------|------------------|
| Retrain `SSRIModel` locally | Weights none; CPU torch already in Docker | Engineer time; electricity |
| Prithvi / Clay weights | Apache-2.0 downloads | GPU fine-tune host |
| Landslide public datasets | Often free downloads | License compliance |
| LLM APIs | Free tiers for **text** | Quotas; not for maps |
| Managed GPU fine-tune | — | Cloud GPU hours |

**Free model weights ≠ free scientifically valid SSRI predictions.** Labels and acquisition are the scarce resources.

---

## 9. Risks, assumptions, unresolved questions

| Item | Type |
|------|------|
| Three-class product without three-class labels | Critical risk |
| Spectral all-nodata | Confirmed on sample; assume endemic until re-acquisition |
| Foundation AUC not transferable to assess sinkhole class | Confirmed taxonomy mismatch |
| Production Render checkpoint path contents | **Unresolved** without authenticated server filesystem access |
| Exact Render RAM | Unknown |
| Client AOI inventories availability | Unresolved business input |

---

## 10. Phased implementation plan (after approval)

| Phase | Action | Outcome gate |
|-------|--------|--------------|
| **0 — Honesty** | Decide: three-class vs landslide-only interim; stop claiming sinkhole/subsidence from USGS-only stacks | Product scope written |
| **1 — Data** | Acquire inventories + rebuild FeatureStacks with real spectral/geophysics; Stage 2.5 layout | Validation `passed`; class counts non-zero |
| **2 — Retrain** | `SSRIModel` (or landslide-only head) with spatial splits; softmax; promote checkpoint | Held-out beats baseline; NOT_VALIDATED remains |
| **3 — Wire** | Point assess at Stage 2.5 `best.pt`; fix sigmoid; CORS/API key | Authenticated live map prediction changes with input |
| **4 — Optional** | LLM explanations (free-first audit) | Text only |
| **5 — Research** | Prithvi/Clay fine-tune **only** if Phase 2 baseline is weak and GPU budget exists | Must beat Phase 2 on same splits |

---

## 11. Acceptance criteria (prediction system)

A “working” SSRI prediction system (still NOT_VALIDATED scientifically until human validation process) requires **all** of:

1. Loadable Stage 2.5 (or scoped) checkpoint with `model_state_dict` + `model_config`.
2. Feature stacks with documented, mostly finite channels used by the model.
3. Labels matching the claimed hazard set.
4. Softmax (or documented binary heads) consistent with loss.
5. Authenticated assess returns spatial or point scores from **that** checkpoint.
6. Perturbation of inputs changes outputs.
7. Held-out spatial metrics beat a simple baseline.
8. UI/API never claim scientific validation unless a separate process completes.

---

## 12. Final recommendation

| Field | Value |
|-------|--------|
| **Decision** | **BLOCKED BY DATA** |
| **Preferred candidate after unblock** | Existing **`SSRIModel` Stage 2.5** retrained on proper labels (free/local CPU) — option **D / RETRAIN** once data exists |
| **Not preferred** | REPLACE with Prithvi/Clay/LLM as the numerical engine |
| **Software REPAIR** | Necessary hygiene (softmax, CORS, keys) but **insufficient** alone |
| **Interim product option** | Landslide-only research path with honest UI — still needs spectral/feature repair |

### Justification (short)

Disk holds multitask **foundation** weights that **assess cannot load**, and a **landslide** FeatureStack set with **empty spectral channels** and **no three-class ground truth**. No free pretrained model maps SSRI’s 13 channels to subsidence/landslide/sinkhole with evidence. Therefore the credible path is **acquire correct labels and features, then retrain the small existing U-Net** (or honestly shrink scope)—not more repair of empty science, and not an EO/LLM replacement fantasy.

Await approval before any implementation.
