# SSRI Implementation Progress

**Master spec:** `docs/SSRI_MASTER_COMPLETION_PROMPT.md`  
**Started:** 2026-09-08  
**Overall status:** IN PROGRESS — **not** scientifically validated

---

## Log

### 2026-09-08 — Phase 0 / Phase 1 engineering
- Baseline + schema + USGS tooling + multitask/DANN/ECE engineering (see prior entries).

### 2026-09-09 — USGS ingest + foundation pilot (v2 / n=80)
- Catalog **251,344** ingested.
- FeatureStacks **v2: 80/80**; experiment `20260909T001911Z`; test tile AUC **0.574** (gate failed).
- OpenTopo 50/day limit → GEE COP30 DEM fallback.

### 2026-09-09 — Priority A: expand + audit + retrain (v3)

**A1 Dataset expansion**
- Built `data/datasets/usgs_landslide_featurestacks/v3`
- **120 positives + 120 documented pseudo-absences = 240** stacks (**0 failed**; 9 reused from v2)
- Splits (2° blocks, seed=7): train **179** / val **33** / test **28**
- CONUS extent ~lat 31.2–48.5, lon −124.5–−67.7; **104** spatial blocks

**A2 Pseudo-absence audit**
- Full-inventory exclusion buffer **15 km** (all CONUS USGS points)
- Inter-absence ≥5 km; positive separation ≥2 km
- Audit: **0** absences inside buffer; min absence→inventory **15.26 km**
- Docs: `docs/SOURCE_PSEUDO_ABSENCE_METHODOLOGY.md`

**A3 Spatial split audit**
- **0** multi-split blocks; min train↔test NN **17.1 km**
- Docs: `docs/SOURCE_SPATIAL_SPLIT_AUDIT.md` + `v3/sampling_audit.json`

**A4 Retrain**
- New experiment **`20260909T025912Z`** (baseline `20260909T001911Z` preserved)
- Checkpoint: `models/ssri-foundation-v2.pt`
- Test tile ROC-AUC **0.750** (was 0.574); PR-AUC **0.815**; pixel F1 **0.818**; ECE **0.094**; Brier tile **0.178**
- Source gate ≥0.88: **FAILED** (honest)

### 2026-09-09 — Priority B: EIGEN-6C4
- Provider fail-closed path via `SSRI_GRAVITY_SOURCE` + `EIGEN6C4_DATA_PATH`
- Manifest label via `resolve_gravity_source_label()` — **never** relabels WGM as EIGEN
- Acquisition guide: `docs/EIGEN6C4_ACQUISITION.md`
- Raster **not yet on disk**; current stacks still `wgm2012_bouguer`

### 2026-09-09 — Priority C: African target
- Investigation: `docs/AFRICAN_TARGET_DATA_STATUS.md`
- UGLC = primary candidate; Zenodo API **HTTP 504** here
- Ingest ready: `python -m ssri_model.scripts.ingest_uglc_africa --local-csv …`
- DANN roles documented (SOURCE / TARGET_UNLABELED / TARGET_HELD_OUT)

### Next uncompleted master-spec stage
**Phase 3 — Direct transfer baseline** once African labelled inventory is on disk (manual UGLC CSV).

### Current honest status
```text
SOURCE PILOT IMPROVED (n=240, test AUC 0.750) — GATE ≥0.88 NOT MET
EIGEN-6C4 INTERFACE READY — RASTER NOT ACQUIRED
PHASE 3 BLOCKED ON AFRICAN TARGET DOWNLOAD
SCIENTIFIC VALIDATION INCOMPLETE
```
