# SSRI — Stage 2.5 Training Data Readiness and Scientific Gap Audit

**Date:** 2026-11-21  
**Mode:** STRICT READ-ONLY  
**Prior context:** `SSRI_STAGE25_CHECKPOINT_DISCOVERY_REPORT.md` (local 13-channel checkpoints are synthetic/rehearsal; no genuine production Stage 2.5 weights identified; scientific status `NOT_VALIDATED`)  
**Scope:** Establish whether existing on-disk real-world data are sufficient to train the Stage 2.5 assessment model (`SSRIModel`, 13 channels, classes subsidence / landslide / sinkhole).

---

## 1. Executive summary

```text
VERDICT: REAL FEATURES FOUND — LABEL ACQUISITION REQUIRED
```

| Question | Finding |
|----------|---------|
| Do real 13-channel feature stacks exist on disk? | **Yes** — USGS landslide FeatureStacks v3 (CONUS, n=240), channels match `CHANNEL_NAMES` |
| Do real geophysical feature layers exist? | **Yes** — WGM2012 gravity + EMAG2v3 magnetics (raw + CONUS/Lagos clips) with provenance |
| Does a Stage 2.5 three-class labelled training package exist? | **No** — only synthetic/rehearsal Stage 2.5 `train/`/`validation/` trees |
| Are verified labels available for all three hazards? | **No** — landslide inventory presence only; subsidence and sinkhole Stage 2.5 labels **NOT FOUND** |
| Can USGS binary labels be used as-is for Stage 2.5? | **No** — semantic mismatch (values 0/1 ≠ mutual exclusive 0/1/2 contract); layout is foundation multitask, not `SSRIDataset` |
| Independent African labelled holdout on disk? | **NOT FOUND** — UGLC Africa ingest directory empty |
| Scientific training readiness | **Not ready**; prior synthetic training runs are not evidence of scientific readiness |

**Counts (this audit):**

| Metric | Count |
|--------|------:|
| Genuine candidate **feature** dataset families | **2** |
| Verified Stage 2.5 **three-class** label datasets | **0** |
| Verified **landslide inventory** label sources on disk | **1** (USGS US Landslide Inventories v3) |

---

## 2. Audit scope and limitations

### In scope

- Stage 2.5 training contract in `model/src/ssri_model/`
- Local and ignored trees: `data/`, `model/outputs/`, `model/tests/`, `poc/`, catalogs, geophysics
- Feature stacks, labels, manifests, provenance docs, geological fixtures
- Read-only probes of `.npy` / `.tif` / JSON (no training, no mutation of datasets)

### Out of scope / not performed

- Training, fine-tuning, evaluation, checkpoint register/promote
- Synthetic data generation or label invention
- Git operations, deploys, env changes, uploads
- Render production filesystem inspection (checkpoint availability remains **NOT_VERIFIED** per prior report)
- Download of external inventories not already on disk (Lagos InSAR, UGLC Zenodo, Florida FGS, NASA COOLR)

### Limitations

- Full SHA-256 of multi-hundred-MB geophysics rasters was not exhaustively computed for every file; sizes and provenance JSON were verified.
- Pixel-level class histograms were sampled on representative USGS tiles, not all 240 samples.
- External candidate inventories documented in `docs/dataset_candidates_report.md` and `docs/AFRICAN_TARGET_DATA_STATUS.md` are **not present** as training packages on this workstation unless noted below.
- Temporary read-only probe scripts under `poc/_tmp_data_readiness_probe*.py` were removed after inspection; they did not alter datasets.

---

## 3. Exact Stage 2.5 training contract

### 3.1 Authoritative paths and symbols

| Role | Path | Symbol |
|------|------|--------|
| Channel order (13) | `model/src/ssri_model/ml/constants.py` | `CHANNEL_NAMES`, `CHANNEL_COUNT=13`, `FEATURE_NODATA=-9999.0`, `LABEL_NODATA=-1` |
| Hazard class names | `model/src/ssri_model/ml/labels.py` | `LabelClass`: `subsidence`, `landslide`, `sinkhole` |
| Dataset loader | `model/src/ssri_model/ml/dataset.py` | `SSRIDataset` |
| Manifest schema | `model/src/ssri_model/ml/dataset_spec.py` | `DatasetManifest`, `FeatureSample` |
| Manifest writer | `model/src/ssri_model/dataset/catalog.py` | `write_manifest` |
| ID split utility | `model/src/ssri_model/ml/splits.py` | `split_sample_ids`, `SplitConfig` (default 70/15/15, seed 42) — **random shuffle of IDs, not spatial blocks** |
| Model | `model/src/ssri_model/architecture/model.py` | `SSRIModel` |
| Model config | `model/src/ssri_model/architecture/config.py` | `SSRIModelConfig(in_channels=13, num_classes=3)` |
| Trainer / checkpoints | `model/src/ssri_model/training/trainer.py`, `training/checkpoint.py` | `Trainer`; `best.pt` / `latest.pt` with `model_state_dict` + `model_config` |
| Schema-v2 extras (not live assess) | `model/src/ssri_model/release_shell/channel_schema.py` | `CHANNEL_NAMES_V2` (+ `overburden_thickness`, `lineament_density`, `lineament_distance`); `depth_to_bedrock` **must not** be aliased to overburden |

### 3.2 Required 13-channel order

Exact order from `CHANNEL_NAMES`:

1. `elevation`  
2. `slope`  
3. `plan_curvature`  
4. `profile_curvature`  
5. `twi`  
6. `relative_relief`  
7. `valley_depth`  
8. `ndvi`  
9. `ndwi`  
10. `clay_mineral_ratio`  
11. `iron_oxide_index`  
12. `gravity`  
13. `magnetics`  

Live assess rejects 16-channel schema-v2 stacks against a 13-channel checkpoint (no pad/truncate/zero-fill).

### 3.3 Label encoding (verified)

Enum definition order in `LabelClass` → integer indices used by `SSRIDataset.label_class_to_index` and documented in `docs/operations.md` / `docs/MANUAL_TRAINING_CLIENT_BRIEFING.md`:

| Integer | Class |
|--------:|-------|
| 0 | `subsidence` |
| 1 | `landslide` |
| 2 | `sinkhole` |
| −1 | nodata / ignore (`LABEL_NODATA`) |

`SSRIDataset._load_label` reads `label.tif`, maps values in `[0, class_count)` or legacy 1-based `[1, class_count]` into class indices, else raises `InvalidLabelError`. Feature validity mask requires **all** channels ≠ `FEATURE_NODATA` at a pixel.

**Do not assume output class count alone defines hazards** — mapping is explicitly `subsidence`/`landslide`/`sinkhole`, **not** foundation multitask `liquefaction`. Sinkhole must not be renamed to liquefaction (`docs/HAZARD_TAXONOMY.md`, `AGENTS.md`).

### 3.4 On-disk Stage 2.5 layout

```text
{dataset}/
  manifest.json          # channels, label_classes, splits.{train,validation,test}, counts
  statistics.json
  train/{id}/feature_stack.npy   # (13, H, W)
  train/{id}/label.tif
  train/{id}/metadata.json
  validation/{id}/...
  test/{id}/...          # optional but supported by splits
```

`SSRIDataset` requires non-empty split directories matching `manifest.splits`. Both train and validation must be non-empty for practical training (product docs).

### 3.5 Spatial vs random split

- **Contract helper** `split_sample_ids`: deterministic **random** ID shuffle — susceptible to spatial leakage if tiles are geographic neighbours.
- **USGS FeatureStacks v3** used a separate **spatial_block_2deg** strategy (documented in dataset manifest + `docs/SOURCE_SPATIAL_SPLIT_AUDIT.md`) — scientifically preferable for that pilot, but **not** the default `SSRIDataset` helper and **not** a three-class Stage 2.5 package.

### 3.6 Related but incompatible contracts

| Stack | Heads / labels | Assess-loadable? |
|-------|----------------|------------------|
| Stage 2.5 `SSRIModel` | Softmax / CE over subsidence, landslide, sinkhole | Yes (13-ch checkpoint) |
| Foundation `SSRIMultiTaskModel` | landslide, subsidence, **liquefaction** (masked BCE; missing ≠ negative) | No |

USGS FeatureStacks store `labels_multitask.npz` with that foundation semantics — **not** Stage 2.5 mutual-exclusive three-class rasters.

---

## 4. Complete dataset inventory

Duplicates of the same family (v1/v2/v3 FeatureStacks; multiple synthetic rehearsal copies) are **not** counted as independent scientific datasets.

### 4.1 Inventory table

| Dataset | Source | Geographic coverage | CRS | Resolution | Channels | Labels | Classification | Readiness |
|---------|--------|---------------------|-----|------------|----------:|--------|----------------|-----------|
| USGS FeatureStacks **v3** | USGS US Landslide Inventories v3 + GEE DEM/spectral + WGM2012/EMAG2 | CONUS (~31–48°N, 124–68°W) | Sample UTM (e.g. EPSG:32614) / WGS84 metadata | 30 m | **13** (exact `CHANNEL_NAMES`) | Binary landslide 0/1; subsidence/liquefaction missing | `REAL_PARTIALLY_VERIFIED` | Features usable as source-domain stacks; **not** Stage 2.5 three-class package |
| USGS FeatureStacks v1/v2 | Same family (earlier pilots) | CONUS | Same pattern | 30 m | 13 | Same binary semantics | `REAL_PARTIALLY_VERIFIED` | Superseded by v3 for counts; not independent |
| USGS landslide catalog v3 | ScienceBase DOI `10.5066/P14AJF8I`, CC0-1.0 | CONUS inventory (~251 344 points in catalog manifest) | Catalog CRS as ingested (CSV) | Points / polygons | N/A (inventory) | Landslide presence only | `REAL_VERIFIED` (inventory) | Label **source** for landslide; not Stage 2.5 raster GT for three hazards |
| WGM2012 + EMAG2v3 geophysics | BGI WGM2012; NOAA/NCEI EMAG2v3 | Global raw; CONUS + Lagos clips | EPSG:4326 (provenance) | ~2′ native | Gravity + magnetics layers | None | `REAL_VERIFIED` (features) | Conditioning / FeatureStack inputs only |
| Stage 2.5 synthetic trees under `model/outputs/*`, `poc/release_shell/outputs/*` | Generated rehearsal | Synthetic / EPSG:4326 tiles | Synthetic | Synthetic (e.g. 128²) | 13 or 16 | Three-class synthetic | `SYNTHETIC` / `FIXTURE_OR_REHEARSAL` | Pipeline rehearsal only — **not** scientific training |
| Geological CSV/GeoJSON fixtures | `model/tests/fixtures/geological/` | Unit-test geometry | Test CRS | N/A | Overburden/lineament test vectors | None (not hazard GT) | `FIXTURE_OR_REHEARSAL` | Tests only |
| `SYNTHETIC_overburden.csv` | `poc/release_shell/outputs/hazard_factors_v2_rehearsal/` | Rehearsal | N/A | N/A | Overburden (conditioning) | None | `SYNTHETIC` | Not hazard labels |
| UGLC Africa catalog | Zenodo planned; ingest scaffold | Africa / Nigeria (intended) | N/A | N/A | N/A | **NOT FOUND on disk** (`data/catalogs/uglc_africa/raw` empty) | `UNKNOWN` / absent | Blocked |
| Lagos InSAR / Florida FGS / NASA COOLR | Documented candidates | Lagos / Florida / global | — | — | — | **NOT FOUND on disk** as SSRI packages | Documented external only | Not inventoryable as local training data |

### 4.2 Key paths and sizes (evidence)

| Path | Size (bytes) | Notes |
|------|-------------:|-------|
| `data/datasets/usgs_landslide_featurestacks/v3/` | 240 sample dirs | Manifest SHA-256 `7af71802…265ee1` |
| `…/samples/usgs-v3-pt90268/feature_stack.npy` | — | Shape `(13, 67, 50)`; SHA-256 `633ac721…d5a0` |
| `data/catalogs/usgs_landslide_v3/catalog.jsonl` | 188 430 943 | Ingested inventory |
| `data/catalogs/usgs_landslide_v3/extracted/us_ls_v3_point.csv` | 118 578 594 | Source points |
| `data/catalogs/usgs_landslide_v3/extracted/us_ls_v3_poly.csv` | 294 784 401 | Source polygons |
| `data/catalogs/usgs_landslide_v3/manifest.json` | 704 | DOI / license / semantics; SHA-256 `26613173…8b201f` |
| `data/geophysics/raw/WGM2012_Bouguer_ponc_2min.grd` | 233 410 500 | Raw gravity |
| `data/geophysics/raw/EMAG2_V3_20170530_UpCont.tif` | 239 593 097 | Raw magnetics |
| `data/geophysics/processed/wgm2012_bouguer_conus.tif` | 4 818 777 | CONUS clip |
| `data/geophysics/processed/emag2v3_conus.tif` | 5 119 792 | CONUS clip |
| `data/geophysics/processed/lagos_gravity_wgm2012_bouguer.tif` | 14 113 | Lagos AOI |
| `data/geophysics/processed/lagos_magnetic_emag2v3_uc4km.tif` | 15 166 | Lagos AOI |
| `data/geophysics/provenance/lagos_geophysics_provenance.json` | 2 882 | Units, DOI, nodata |
| `model/outputs/rehearsal_300k_shell/.../ds_8105d14a825d/data/` | — | `SYNTHETIC-300k-rehearsal`, 13-ch, label_classes three-class |
| `model/tests/fixtures/geological/*` | small | Test fixtures only |

---

## 5. Feature data assessment

### 5.1 USGS FeatureStacks v3 (primary genuine feature+label pilot)

| Property | Evidence |
|----------|----------|
| Real observations? | **Partially** — landslide **locations** from USGS inventory; terrain/spectral from GEE (`dem_provider: gee`); gravity/magnetics from documented public grids |
| Source org | USGS ScienceBase `10.5066/P14AJF8I`; BGI; NOAA/NCEI |
| Acquisition | Built 2026-09-09 (`created_at` in manifest); inventory version 3.0 |
| Extent | CONUS; sample e.g. lon −99.24, lat 41.28 |
| Channel count / order | **13**, matches `CHANNEL_NAMES` exactly in sample `metadata.json` |
| Missing values | `FEATURE_NODATA=-9999`; sampled positive tile had substantial nodata pixels in stack |
| Alignment | Features and `label.tif` share H×W; CRS per-sample UTM |
| Reproducibility | Documented pipeline + catalog on disk; GEE extraction requires credentials/environment **NOT VERIFIED** in this audit |
| Stage 2.5 folder contract | **No** — uses `samples/{id}/` + multitask NPZ, not `train/`/`validation/` Stage 2.5 layout |

**Classification:** `REAL_PARTIALLY_VERIFIED` — real inventory-anchored features; not a finished Stage 2.5 scientific training package.

### 5.2 Geophysics package

| Layer | Source | Units | CRS | Role |
|-------|--------|-------|-----|------|
| WGM2012 Bouguer | BGI DOI `10.18168/bgi.23` | mGal | EPSG:4326 | Feature channel `gravity` |
| EMAG2v3 UC 4 km | NOAA DOI `10.7289/V5H70CVX` | nT | EPSG:4326 | Feature channel `magnetics` |

Provenance explicitly warns that resampling ~2′ grids to 30 m **does not create new geophysical information**. Lagos clips exist for AOI demos; they are **unlabelled** for Stage 2.5 hazards.

**Classification:** `REAL_VERIFIED` as feature layers; `REAL_UNLABELLED` as training samples.

### 5.3 Synthetic / rehearsal feature stacks

Hundreds of `feature_stack.npy` under ignored output trees (e.g. `(13, 128, 128)` rehearsal; `(16, …)` schema-v2). Dataset names include `SYNTHETIC-300k-rehearsal`, `SYNTHETIC_stage25_template`, `SYNTHETIC_stage25_v2_template`.

**Classification:** `SYNTHETIC` / `FIXTURE_OR_REHEARSAL` — must not be promoted as real training data.

### 5.4 Schema-v2 / conditioning channels

`CHANNEL_NAMES_V2` adds overburden and lineament metrics. **No real regional overburden/lineament FeatureStacks** for scientific training were found on disk (only fixtures + `SYNTHETIC_overburden.csv`). Live assess remains 13-channel; conditioning must not be treated as changing current live scores.

---

## 6. Hazard label assessment

### 6.1 Subsidence

| Field | Status |
|-------|--------|
| Real positive Stage 2.5 labels on disk | **NOT FOUND** |
| Verified negatives | **NOT FOUND** |
| USGS FeatureStacks | `subsidence: null` / multitask arrays filled with −9999; mask 0 |
| Documented external candidates | Lagos InSAR VLM (BENCHMARK-ONLY per `docs/dataset_candidates_report.md`) — **not downloaded** as SSRI `label.tif` |
| Status | **UNSUPPORTED for Stage 2.5 scientific training** |

### 6.2 Landslide

| Field | Status |
|-------|--------|
| Real positive labels | **Yes** — USGS inventory presence; FeatureStacks v3: **120** positive samples (`usgs-v3-*`); catalog ~251 344 points |
| “Negatives” | **120** documented **pseudo-absences** — explicit flags `not_field_confirmed_absence` (`docs/SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md`). **Not** field-verified absences |
| Label rasters | Sampled positive `label.tif`: all pixels **1**; pseudo-absence: all pixels **0** |
| If fed naïvely to Stage 2.5 | Value `0` → class **subsidence**; value `1` → class **landslide** — **semantic corruption** of three-class contract |
| Geographic coverage | CONUS only on disk |
| African / Nigeria labelled holdout | **NOT FOUND** (UGLC raw empty) |
| Status | **PARTIAL** — defensible as **binary landslide inventory pilot**; **not** Stage 2.5 three-class GT |

### 6.3 Sinkhole

| Field | Status |
|-------|--------|
| Real positive Stage 2.5 labels on disk | **NOT FOUND** (zero files matching sinkhole inventories in `data/` / `poc/` / `model/datasets`) |
| Verified negatives | **NOT FOUND** |
| Documented external | Florida FGS incidents (weak, Florida-only, mostly unverified) — **not on disk** |
| Status | **UNSUPPORTED** |

### 6.4 Hazards remaining unsupported for Stage 2.5

Explicitly: **subsidence** and **sinkhole** lack adequate Stage 2.5 labels. Landslide lacks three-class mutual-exclusive encoding and African holdout. **Do not drop** any of the three intended SSRI hazards; acquire labels instead.

---

## 7. Geological conditioning data assessment

| Variable | On-disk status | Source / notes |
|----------|----------------|----------------|
| `overburden_thickness` | Fixtures + synthetic CSV only | `model/tests/fixtures/geological/regular.csv` etc.; `SYNTHETIC_overburden.csv` |
| `depth_to_bedrock` | Fixture candidate CSV only | Explicitly **distinct** from overburden (`channel_schema.py`); no silent alias |
| `lineament_density` / `lineament_distance` | Tiny GeoJSON fixture | `model/tests/fixtures/geological/lineaments.geojson` (276 B) |
| Geological maps / lithology | **NOT FOUND** as training rasters | NGSA maps documented as context-only in African status doc |
| Effect on live assess scores | **None claimed** | Live model remains 13-channel; Phase 6 schema-v2 blocked |

These are **features / conditioning**, not hazard labels.

---

## 8. Provenance classification

| Candidate | Classification | Evidence |
|-----------|----------------|----------|
| USGS catalog + FeatureStacks v3 | `REAL_PARTIALLY_VERIFIED` | DOI, CC0, ScienceBase landing page, inventory IDs, documented GEE/geophysics sources; pseudo-absences not field-confirmed |
| Geophysics raw/processed | `REAL_VERIFIED` | Provenance JSON with DOI, units, CRS, archive URL for WGM2012 |
| Stage 2.5 rehearsal datasets / checkpoints | `SYNTHETIC` / `FIXTURE_OR_REHEARSAL` | Dataset names, paths under `outputs/`, prior checkpoint discovery report |
| Geological fixtures | `FIXTURE_OR_REHEARSAL` | Under `tests/fixtures` |
| UGLC Africa | Absent / `UNKNOWN` | Empty `raw/` |
| Filename without “synthetic” | — | **Not** used as evidence of reality |

---

## 9. Geographic alignment and leakage assessment

### USGS v3 (landslide binary pilot)

| Check | Result |
|-------|--------|
| Split strategy | `spatial_block_2deg` (seed documented in audit) |
| Blocks in >1 split | **0** (`docs/SOURCE_SPATIAL_SPLIT_AUDIT.md`) |
| Min train↔test NN | **17.1 km** |
| Residual autocorrelation | Possible at long range (documented limitation) |
| Temporal independence of labels | **NOT VERIFIED** as event-date holdout; inventory is presence-based |
| Validation label independence | Same USGS catalog family; spatial holdout only |

### Stage 2.5 default splitter

`split_sample_ids` is **random ID shuffle**. Using it on spatially adjacent tiles would **inflate** metrics via spatial autocorrelation. No real Stage 2.5 three-class package exists to audit for leakage today.

### Synthetic Stage 2.5 trees

Not scientifically relevant for leakage claims.

### Independent geographic holdout for target domain

African labelled holdout: **NOT FOUND** on disk → independent spatial validation for the product AOI is **not currently possible**.

---

## 10. Dataset readiness tables

### Dataset inventory (summary)

| Dataset | Source | Geographic coverage | CRS | Resolution | Channels | Labels | Classification | Readiness |
|---|---|---|---|---|---:|---|---|---|
| USGS FeatureStacks v3 | USGS + GEE + WGM/EMAG2 | CONUS | UTM / WGS84 | 30 m | 13 | Binary LS only | `REAL_PARTIALLY_VERIFIED` | Features OK; Stage 2.5 GT gap |
| USGS catalog v3 | ScienceBase | CONUS | CSV | Points/polys | — | LS presence | `REAL_VERIFIED` | Inventory only |
| Geophysics WGM+EMAG2 | BGI / NOAA | Global + Lagos/CONUS clips | EPSG:4326 | ~2′ | 2 layers | None | `REAL_VERIFIED` | Features only |
| Synthetic Stage 2.5 outputs | Rehearsal generators | Synthetic | Synthetic | Synthetic | 13/16 | Synthetic 3-class | `SYNTHETIC` | Not scientific |
| Geological fixtures | Tests | N/A | N/A | N/A | Conditioning | None | `FIXTURE_OR_REHEARSAL` | Tests only |
| UGLC Africa | Planned Zenodo | Africa | — | — | — | NOT FOUND | Absent | Blocked |

### Hazard label readiness

| Hazard | Real positive labels | Verified negatives | Label source | Geographic coverage | Feature alignment | Independent holdout | Status |
|---|---|---|---|---|---|---|---|
| Subsidence | **NOT FOUND** (Stage 2.5) | **NOT FOUND** | — | — | — | **NOT FOUND** | **NOT READY** |
| Landslide | 120 FeatureStack positives (+ ~251k catalog points) | **0 field-verified**; 120 pseudo-absences | USGS US LS Inventories v3 | CONUS | 13-ch stacks aligned to binary rasters | Spatial blocks within CONUS; Africa **NOT FOUND** | **PARTIAL** (binary only; not Stage 2.5 3-class) |
| Sinkhole | **NOT FOUND** | **NOT FOUND** | — | — | — | **NOT FOUND** | **NOT READY** |

### Scientific training requirements

| Requirement | Current evidence | Missing evidence | Required action |
|---|---|---|---|
| Real feature data | USGS 13-ch CONUS stacks; WGM/EMAG2 | African FeatureStacks with full 13 channels | Build target-domain stacks from documented sources |
| Verified hazard labels | USGS landslide presence | Subsidence + sinkhole inventories; field-verified negatives | Acquire authoritative inventories; encode as Stage 2.5 `label.tif` |
| 13-channel compatibility | USGS stacks match `CHANNEL_NAMES` | Stage 2.5 package layout | Convert/remap carefully; **do not** zero-fill or drop channels from v2 |
| Geographic alignment | Per-sample UTM alignment in USGS | Cross-hazard co-registered labels on same grid | Align all hazard labels to feature grids |
| Spatially independent split | USGS 2° blocks | Stage 2.5 spatial split implementation on real 3-class data | Prefer spatial blocks over `split_sample_ids` random shuffle |
| Class balance | USGS 120/120 binary | Three-class balance unknown (no data) | Stratify after multi-hazard labels exist |
| Independent test data | CONUS spatial test (binary) | Independent region + all three hazards | Geographic holdout (e.g. Africa) with labels unused in training |
| Reproducible provenance | Catalog DOI + geophysics provenance | End-to-end FeatureStack rebuild recipe verified this session | Document GEE/export pins; store durable artifacts off Render Free |

---

## 11. Hazard readiness tables

*(See §10 hazard table — authoritative summary.)*

| Hazard | Readiness one-liner |
|--------|---------------------|
| Subsidence | **NOT READY** — no Stage 2.5 positives/negatives on disk |
| Landslide | **PARTIAL** — real CONUS inventory + 13-ch features; wrong label contract for Stage 2.5; no African holdout |
| Sinkhole | **NOT READY** — no inventory on disk |

---

## 12. Overall scientific training verdict

```text
REAL FEATURES FOUND — LABEL ACQUISITION REQUIRED
```

### Why this verdict (not others)

| Option | Why rejected / accepted |
|--------|-------------------------|
| `READY FOR SCIENTIFIC TRAINING` | Rejected — three-class GT absent; validation status remains research-only |
| `PARTIALLY READY — DATA PREPARATION REQUIRED` | Too optimistic — preparation cannot invent missing subsidence/sinkhole inventories |
| **`REAL FEATURES FOUND — LABEL ACQUISITION REQUIRED`** | **Selected** — genuine 13-ch features + landslide inventory exist; Stage 2.5 training blocked on labels |
| `NO SUITABLE REAL TRAINING DATA FOUND` | Rejected — USGS stacks and geophysics are real |
| `INSUFFICIENT EVIDENCE` | Rejected — enough local evidence to decide label gap |

### Explicit answers

1. **Genuine datasets already present:** USGS FeatureStacks v3 (and earlier versions), USGS landslide catalog v3, WGM2012/EMAG2 geophysics with provenance.  
2. **Hazards with defensible labels:** Landslide **presence** (USGS) only — and only as binary inventory semantics.  
3. **Hazards lacking adequate labels:** Subsidence and sinkhole (Stage 2.5); landslide lacks three-class encoding and target-domain holdout.  
4. **Can 13-channel architecture be used without modification?** **Yes** for the model/API contract — once a compliant dataset exists. No need to change `SSRIModel` channel count for scientific Stage 2.5 training. Do **not** silently use 16-channel schema-v2.  
5. **Independent spatial validation possible today?** **Only** within the USGS binary CONUS pilot (2° blocks). **Not** for three-class Stage 2.5 or African product AOI.  
6. **Minimum work before training:** Acquire/verify subsidence and sinkhole inventories (plus landslide encoding rules), build Stage 2.5 `label.tif` packages co-registered to 13-ch stacks, define spatial holdouts, then train — still marking `NOT_VALIDATED` until scientific review.

A successful synthetic rehearsal train is **not** scientific readiness.

---

## 13. Prioritized next steps

### A. Existing data to preserve

- `data/datasets/usgs_landslide_featurestacks/v3/` (+ v1/v2 as lineage)
- `data/catalogs/usgs_landslide_v3/` (catalog.jsonl, CSVs, manifest)
- `data/geophysics/raw/` and `processed/` + `provenance/lagos_geophysics_provenance.json`
- Docs: `SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md`, `SOURCE_SPATIAL_SPLIT_AUDIT.md`, `AFRICAN_TARGET_DATA_STATUS.md`, `dataset_candidates_report.md`
- Do **not** overwrite USGS v3 baseline noted in its manifest

### B. Data requiring verification

- Positional accuracy / confidence fields in USGS catalog vs FeatureStack centroids
- Whether any Lagos InSAR deposit is already cached outside audited trees (**NOT FOUND** here)
- License/terms before redistributing WGM2012 / inventory extracts
- Exact CRS and units if any client geological CSVs appear later (`depth_to_bedrock` vs `overburden_thickness`)

### C. Data preparation (after labels exist)

- Build Stage 2.5 directory layout via `write_manifest` / `SSRIDataset` contract
- Remap landslide presence to class index **1** with surrounding nodata **−1** (never coerce unknown → class 0)
- Reject any conversion of binary 0/1 rasters that would mark absences as `subsidence`
- Compute `statistics.json`; QC nodata; no channel drop from schema-v2 without a new model

### D. Label acquisition (highest priority)

| Hazard | Needed evidence |
|--------|-----------------|
| Subsidence | Authoritative occurrence inventory or approved protocol converting VLM → labels (currently none approved); dates, CRS, accuracy |
| Landslide | Keep USGS as source domain; acquire African inventory (e.g. UGLC manual Zenodo fetch) for holdout |
| Sinkhole | Geological-survey or field-validated sinkhole inventory co-located with features; do not use susceptibility maps as GT |

Do not treat unrecorded locations as negatives without evidence.

### E. Validation preparation

- Spatial block (or buffered geographic) splits for any Stage 2.5 package
- Independent region holdout (target AOI) never used for training/tuning
- Document that pseudo-absences ≠ verified negatives in metrics interpretation

### F. Infrastructure

- Durable shared storage for datasets, registries, and checkpoints (API + worker) — **do not assume Render Free `/data` durability**
- Train only after data readiness; paid GPU optional later — **not** the next spend gate

---

## 14. Exact source paths and code references

| Item | Reference |
|------|-----------|
| Channels | `model/src/ssri_model/ml/constants.py` → `CHANNEL_NAMES` |
| Classes | `model/src/ssri_model/ml/labels.py` → `LabelClass` |
| Loader | `model/src/ssri_model/ml/dataset.py` → `SSRIDataset._load_features`, `_load_label` |
| Manifest write | `model/src/ssri_model/dataset/catalog.py` → `write_manifest` |
| Random split | `model/src/ssri_model/ml/splits.py` → `split_sample_ids` |
| Model | `model/src/ssri_model/architecture/config.py` → `SSRIModelConfig` |
| Schema v2 | `model/src/ssri_model/release_shell/channel_schema.py` |
| USGS v3 | `data/datasets/usgs_landslide_featurestacks/v3/manifest.json` |
| USGS catalog | `data/catalogs/usgs_landslide_v3/manifest.json` |
| Geophysics provenance | `data/geophysics/provenance/lagos_geophysics_provenance.json` |
| Spatial split audit | `docs/SOURCE_SPATIAL_SPLIT_AUDIT.md` |
| Pseudo-absence method | `docs/SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md` |
| African status | `docs/AFRICAN_TARGET_DATA_STATUS.md` |
| External candidates | `docs/dataset_candidates_report.md` |
| Taxonomy | `docs/HAZARD_TAXONOMY.md` |

---

## 15. Uncertainties and unresolved questions

1. Can Lagos InSAR VLM be ethically/scientifically converted into Stage 2.5 `subsidence` labels? **Unresolved** — currently BENCHMARK-ONLY.  
2. Will UGLC Nigeria density support a meaningful holdout after manual download? **NOT VERIFIED** (files absent).  
3. Are any client-confidential inventories available offline outside this repo tree? **UNKNOWN** — not inspected.  
4. Production Render durable storage for future real checkpoints: **NOT_VERIFIED**.  
5. Full rebuild reproducibility of GEE FeatureStacks in this environment: **NOT VERIFIED** this session.  
6. Pixel-wise class histograms across all 240 USGS tiles: sampled only; global balance assumed from selection audit (120/120).

---

## 16. Explicit confirmation of non-mutation

This audit:

- Did **not** train, fine-tune, or evaluate a model  
- Did **not** generate synthetic datasets or invent labels  
- Did **not** modify source code, datasets, manifests, or configurations (deliverable report only; temporary probe scripts removed)  
- Did **not** move, rename, or delete scientific data files  
- Did **not** register, activate, or promote checkpoints  
- Did **not** change environment variables  
- Did **not** perform Git operations, commits, or pushes  
- Did **not** deploy services or upload data to external services  
- Did **not** promote rehearsal/synthetic artifacts as real datasets  
- Did **not** treat missing labels as safe negatives  

Scientific validation status remains **`NOT_VALIDATED`**.

---

*End of report.*
