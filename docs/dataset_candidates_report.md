# SSRI Dataset Candidates Report (A1 discovery)

**Date:** 2026-09-08 (discovery); updated 2026-09-08 (Lagos InSAR qualification)  
**Scope:** Discovery, vetting, and scientific-data qualification. No datasets were downloaded into the training pipeline. No training was performed. This report does **not** declare A1 unblocked.  

**Repo hazard targets (authoritative):** from `model/src/ssri_model/ml/labels.py` / `SUPPORTED_LABELS`:

| Index | Class |
|-------|--------|
| 0 | `subsidence` |
| 1 | `landslide` |
| 2 | `sinkhole` |

**Feature channels (context only):** 13 Stage-1 channels in `CHANNEL_NAMES` (terrain, spectral, gravity, magnetics) at ~30 m target grid — labels must align to that contract eventually; this report does not assume any candidate already matches that raster label format.

**Not an SSRI training class:** flood / inundation. Flood datasets are listed only as adjacent Nigeria risk data and are **not** usable as like-for-like labels for the three classes above.

---

## Summary table (sorted by fit)

| Fit | Name | Hazard | Geography | License (as documented) |
|-----|------|--------|-----------|-------------------------|
| **BENCHMARK-ONLY** | Ohenhen & Shirzaei Lagos InSAR + risk maps (VT `10.7294/19738957`) | subsidence **reference** (VLM / building-collapse risk) — **not** SSRI `label.tif` | **Lagos, Nigeria** | Dataset v1 deposit: **CC0 1.0**; paper CC BY-NC 4.0; confirm v2 license before production |
| **Partial** | Shirzaei et al. multi-city coastal InSAR VLM (VT 25864435) | subsidence (VLM rates) | 17 cities incl. **Lagos** (+ Abidjan, etc.) | Repository deposit; verify license before commercial use |
| **Partial** | NASA COOLR / Global Landslide Catalog | landslide (rainfall-triggered reports) | Global; **Africa sparse / biased**; Lagos not a dense inventory AOI | NASA open data + required citations; agree to terms on export |
| **Weak** | NASA GLC one-time CSV export (data.nasa.gov) | landslide | Global snapshot (stale vs Landslide Viewer) | NASA open data; citation required; “License not specified” on some portal rows |
| **Weak** | Florida FGS Subsidence Incident Reports | sinkhole / unverified subsidence incidents | **Florida, USA only** | FDEP public GIS; no warranty; not for Nigeria |
| **Weak** | UNOSAT / HDX Nigeria flood water extents | flood (not SSRI class) | Nigeria (events vary; not Lagos-specific labels for SSRI) | Often **CC BY-SA** (share-alike) — can constrain proprietary products |
| **Not usable** | GFDRR ThinkHazard! Nigeria landslide level | landslide susceptibility class (admin unit) | Nigeria (admin aggregation) | **Underlying LS dataset for NGA not publicly downloadable** (licensing) |
| **Not usable** | NGSA geological / litho-structural maps | geology proxy, not hazard events | Nigeria | Public map products; **not event inventories**; access/terms vary by product |
| **Not usable** | Project Floodgate Lagos FRI layers | flood risk index (modeled) | Lagos | Workflow/open GEE inputs; **not** field-validated SSRI labels; flood ≠ SSRI class |
| **Not usable (as training labels)** | Geospatial Atlas of Nigeria (Zenodo) | DEM / physiography | Nigeria | Open-access atlas PDF/maps — **features, not hazard labels** |

---

## Per-candidate detail

### 1. Data for Land Subsidence Hazard and Building Collapse Risk in Lagos (Ohenhen & Shirzaei)

- **Name:** Data for Land Subsidence Hazard and Building Collapse Risk in the Coastal City of Lagos, West Africa  
- **Source / URL:** https://doi.org/10.7294/19738957 (also `.v2`); paper https://doi.org/10.1029/2022EF003219  
- **Hazard class(es) covered:** `subsidence` (InSAR vertical land motion + derived structural risk maps). Building-collapse catalog is **not** sinkhole inventory.  
- **Geographic coverage:** Lagos, Nigeria (target AOI).  
- **Spatial/temporal resolution:** Sentinel-1 InSAR over ~2018–2021; risk maps described at **0.2 km** grid in the paper; VLM from multi-temporal InSAR (not identical to SSRI’s 30 m FeatureStack labels).  
- **Label quality / ground-truth method:** Remote-sensing VLM (InSAR), not field survey of “subsidence events.” Risk layers are **modeled** (angular distortion + building density). Collapse table (~106 compiled records) is a separate catalog with acknowledged incompleteness. GNSS comparison is limited (paper notes sparse validation).  
- **License / usage restrictions:** Dataset deposit **v1** page states **CC0 1.0 Public Domain Dedication** (External source, 2026-09-08). Accompanying paper is **CC BY-NC 4.0**. Confirm **v2** license on the live repository before production use.  
- **Approximate size:** One city-scale VLM point/raster product set; 4 risk GeoTIFF/CSV horizons; ~106 building-collapse rows. Exact VLM point count **not verified** without download.  
- **Fit assessment:** **BENCHMARK-ONLY** (see full qualification § below) — Lagos-aligned VLM/risk reference; **not** SSRI pixel hazard labels; **not** training-suitable without a separate approved protocol (none authorized here).  
- **Key gaps:** Continuous VLM ≠ binary/multi-class pixel labels; risk maps mix deformation with building density; ~75 m InSAR spacing / 200 m risk grid vs SSRI 30 m; landslide/sinkhole absent; A1 not unblocked.  

### 2. InSAR-Based Coastal Land Subsidence (multi-city VLM)

- **Name:** InSAR-Based Coastal Land Subsidence  
- **Source / URL:** https://doi.org/10.7294/25864435  
- **Hazard class(es) covered:** `subsidence` (VLM cm/yr + uncertainty).  
- **Geographic coverage:** 17 coastal cities including **Lagos** (also Abidjan, Dar es Salaam, etc.). Useful for multi-city transfer experiments; not Lagos-only.  
- **Spatial/temporal resolution:** Per-city CSV of lon/lat/incidence/VLM/σ; native InSAR resolution not restated as a uniform grid matching SSRI 30 m.  
- **Label quality / ground-truth method:** InSAR-derived rates (remote sensing), city-by-city processing.  
- **License / usage restrictions:** Same repository family as (1) — **verify license before production**.  
- **Approximate size:** 17 CSV files (one per city); Lagos file size/record count **not verified** without download.  
- **Fit assessment:** **Partial** — strengthens subsidence AOI coverage and possible domain transfer; still deformation rates, not SSRI label tensors.  
- **Key gaps:** Same as (1) for label format; multi-city mix can help or hurt Lagos specificity; no landslide/sinkhole.

### 3. NASA Cooperative Open Online Landslide Repository (COOLR) / Global Landslide Catalog

- **Name:** NASA COOLR (includes GLC + added inventories)  
- **Source / URL:** https://landslides.nasa.gov/viewer ; methodology https://doi.org/10.1371/journal.pone.0218657 ; related open inventories note >11 000 GLC reports + additional inventories (e.g. Figshare https://doi.org/10.6084/m9.figshare.26972467)  
- **Hazard class(es) covered:** `landslide` (rainfall-triggered mass movements; media/report/inventory sourced).  
- **Geographic coverage:** Global. **Africa is under-reported**; literature on GLC notes sparse African reporting, poor location accuracy in places, clusters more toward East African Rift than Lagos coastal plain. **Not a Lagos inventory.**  
- **Spatial/temporal resolution:** Point/event reports with variable location accuracy (often km-scale). Not polygon inventories at 30 m.  
- **Label quality / ground-truth method:** Heterogeneous — news, citizen science, imported expert inventories; quality and completeness vary by region.  
- **License / usage restrictions:** Downloadable via Landslide Viewer (gdb/csv/shp) with NASA terms; cite Kirschbaum et al. / Juang et al. as requested. Generally treated as open scientific data; confirm current terms on export.  
- **Approximate size:** On order of **>11 000** GLC-derived reports in COOLR (plus additional inventory polygons in newer releases — exact Lagos/Nigeria count **not verified** here).  
- **Fit assessment:** **Partial** as a **global landslide prior / transfer-learning source**; **Weak to Not usable** if the requirement is Lagos/Nigeria ground truth at SSRI resolution.  
- **Key gaps:** Geography mismatch for Lagos qualification; event points ≠ dense raster labels; reporting bias; rainfall-trigger focus may miss other failure modes.

### 4. NASA Global Landslide Catalog Export (data.nasa.gov snapshot)

- **Name:** Global Landslide Catalog Export  
- **Source / URL:** https://data.nasa.gov/dataset/global-landslide-catalog-export  
- **Hazard class(es) covered:** `landslide`  
- **Geographic coverage:** Global snapshot (portal notes export dated ~2016; Landslide Viewer is newer).  
- **Spatial/temporal resolution:** Same class of event reports as GLC.  
- **Label quality / ground-truth method:** Media/disaster/scientific reports.  
- **License / usage restrictions:** NASA open data portal; citation required; some resource metadata lists **“License not specified.”**  
- **Approximate size:** One-time CSV export; prefer COOLR Viewer for current counts.  
- **Fit assessment:** **Weak** — superseded by COOLR for freshness; same geographic gaps.  
- **Key gaps:** Staleness; same Africa/Lagos sparsity; not SSRI raster labels.

### 5. Florida FGS Subsidence Incident Reports

- **Name:** Florida Subsidence Incident Reports  
- **Source / URL:** https://geodata.dep.state.fl.us/datasets/florida-subsidence-incident-reports/about ; overview https://floridadep.gov/fgs/sinkholes/content/subsidence-incident-reports  
- **Hazard class(es) covered:** Reported as **subsidence incidents**; may include true sinkholes but **most are unverified**. Closest public **sinkhole-adjacent** event database found.  
- **Geographic coverage:** **Florida, USA only** — different climate, lithology, and failure processes than Lagos coastal sediments.  
- **Spatial/temporal resolution:** Point incident reports (1954–present, voluntary reporting).  
- **Label quality / ground-truth method:** Citizen/agency reports; FGS states majority **not field-verified** as true sinkholes.  
- **License / usage restrictions:** FDEP public GIS with **explicit no-warranty disclaimer**; intended as public information, not certified ground truth.  
- **Approximate size:** Statewide multi-decade incident database (exact count **not verified** this session).  
- **Fit assessment:** **Weak** — useful only as a **methodological / transfer** experiment for sinkhole-like labels, **not** as Lagos sinkhole truth.  
- **Key gaps:** Wrong continent; label noise; reporting bias to populated areas; not production Lagos sinkhole training data.

### 6. UNOSAT / HDX Nigeria flood water extents (adjacent only)

- **Name:** Satellite-detected water extents over Nigeria (multiple event products; e.g. FL20240902NGA mirrors)  
- **Source / URL:** Humanitarian Data Exchange / UNOSAT; example mirrors on Hugging Face citing HDX (e.g. electricsheepafrica Nigeria water-extent datasets)  
- **Hazard class(es) covered:** **Flood / standing water** — **not** an SSRI `SUPPORTED_LABELS` class.  
- **Geographic coverage:** Nigeria (event-dependent; national VIIRS analyses are coarse vs Lagos AOI training).  
- **Spatial/temporal resolution:** Event maps; VIIRS-scale national products are coarse; some Sentinel-1 event products elsewhere are finer but still flood extents.  
- **Label quality / ground-truth method:** Satellite water detection; UNOSAT notes preliminary / not field-validated.  
- **License / usage restrictions:** Commonly **CC BY-SA** on HDX UNOSAT products — **share-alike** can restrict closed-source commercial derivatives; confirm per dataset.  
- **Approximate size:** Per-event polygons/areas (km² scale), not per-pixel SSRI tiles.  
- **Fit assessment:** **Not usable** for training SSRI’s three hazard heads (wrong label semantics). Listed only because the task asked to search flood records.  
- **Key gaps:** Flood ≠ subsidence/landslide/sinkhole; share-alike license risk; wrong task definition.

### 7. GFDRR ThinkHazard! Nigeria — Landslide

- **Name:** ThinkHazard! Nigeria landslide hazard level  
- **Source / URL:** https://int.thinkhazard.org/en/report/NGA-nigeria/LS  
- **Hazard class(es) covered:** Landslide **susceptibility class** at administrative aggregation (Nigeria rated Medium in UI).  
- **Geographic coverage:** Nigeria (admin units).  
- **Spatial/temporal resolution:** Classification of admin units — not 30 m labels.  
- **Label quality / ground-truth method:** Processed from global/index sources per ThinkHazard methods docs.  
- **License / usage restrictions:** UI states the dataset used to classify Nigeria landslide hazard is **not publicly available to view or download due to licensing restrictions**.  
- **Approximate size:** N/A (classification product, not an inventory).  
- **Fit assessment:** **Not usable** as training labels.  
- **Key gaps:** No downloadable labels; admin-scale; not event inventory; license blocked.

### 8. Nigeria Geological Survey Agency (NGSA) maps

- **Name:** Geological sheet maps / Litho-structural Map of Nigeria  
- **Source / URL:** https://ngsa.gov.ng/geological-maps/ ; https://ngsa.gov.ng/litho-structural-map-of-nigeria/  
- **Hazard class(es) covered:** Geology / structure — **proxy only**, not labeled landslide/subsidence/sinkhole events.  
- **Geographic coverage:** Nigeria.  
- **Spatial/temporal resolution:** Map sheets (e.g. 1:100k / 1:250k / 1:2M litho-structural).  
- **Label quality / ground-truth method:** Geological mapping programs; not hazard occurrence databases.  
- **License / usage restrictions:** Government map products; redistribution/commercial terms **not fully documented** on the pages reviewed — treat as **request/confirm with NGSA** before production embedding.  
- **Approximate size:** National map series (not event counts).  
- **Fit assessment:** **Not usable** as A1 hazard labels (possible **feature** context later, out of scope here).  
- **Key gaps:** No event labels; karst/sinkhole inventories for Lagos not published as open event DBs; academic Mfamosing karst descriptions are local SE Nigeria case studies without a public national sinkhole inventory.

### 9. Project Floodgate (Lagos flood risk index)

- **Name:** Project Floodgate  
- **Source / URL:** https://github.com/kayeneii/Floodgate  
- **Hazard class(es) covered:** Flood risk index from CHIRPS + SRTM + HydroSHEDS (modeled).  
- **Geographic coverage:** Lagos State.  
- **Spatial/temporal resolution:** UTM 31N rasters (project docs); seasonal window examples.  
- **Label quality / ground-truth method:** Modeled index from open climate/terrain layers — **not** field hazard validation.  
- **License / usage restrictions:** GitHub workflow; inputs have their own licenses (CHIRPS, SRTM, HydroSHEDS).  
- **Approximate size:** Project raster outputs (not event inventory).  
- **Fit assessment:** **Not usable** for SSRI A1 (wrong hazard; modeled proxy).  
- **Key gaps:** Flood ≠ SSRI classes; circular risk if used as “truth.”

### 10. Geospatial Atlas of Nigeria (Zenodo)

- **Name:** Geospatial Atlas of Nigeria  
- **Source / URL:** https://zenodo.org/records/14930702  
- **Hazard class(es) covered:** None (DEM, LGA, population, terrain derivatives).  
- **Geographic coverage:** Nigeria.  
- **Spatial/temporal resolution:** Atlas map products.  
- **Label quality / ground-truth method:** N/A (not hazard labels).  
- **License / usage restrictions:** Described as open-access; confirm Zenodo record license before redistribution.  
- **Approximate size:** Atlas PDF (~40 MB class) — not training labels.  
- **Fit assessment:** **Not usable** as hazard labels.  
- **Key gaps:** Features only.

---

## Per-hazard conclusions

### subsidence

**Strong public candidate for Lagos as SSRI label.tif?** **No.**  
**Best available public reference:** Ohenhen/Shirzaei Lagos InSAR deposit — **BENCHMARK-ONLY** after qualification (see section below).  

Honest statement: Peer-reviewed Lagos **vertical land motion (VLM)** and derived **building-collapse risk** products exist and are publicly deposited. They are **independent of SSRI FeatureStack channels** (no InSAR in CHANNEL_NAMES). They are **not** SSRI multi-class pixel hazard labels. Forcing VLM or risk codes into subsidence=1 / non-subsidence=0 without a separately approved scientific protocol is **not** authorized by this qualification.

### landslide

**Status:** PUBLIC_LAGOS_DATA_NOT_FOUND

**Strong public candidate for Lagos/Nigeria dense inventory?** **No.**  

NASA COOLR/GLC is the best open **global** landslide event resource found, but Africa reporting is sparse and biased, location accuracy is often poor, and Lagos coastal terrain is not represented as a dense polygon inventory. ThinkHazard Nigeria landslide classification is **not downloadable**.  

**Honest conclusion:** **No public dataset adequately covers landslide + Lagos/Nigeria at SSRI needed label density.** Global inventories are at best a **weak transfer prior** — not a substitute for a Lagos inventory.

**Institutional dataset that would satisfy:** Mapped landslide / slope-failure **polygons or verified points** for Lagos State or comparable SW Nigeria coastal/deltaic terrain, with documented field or photo-interpretation protocol, CRS, date, and license permitting research (and preferably commercial) reuse; dense enough to align to ~30 m grids or to support spatial cross-validation.

### sinkhole

**Status:** PUBLIC_LAGOS_DATA_NOT_FOUND

**Strong public candidate for Lagos/Nigeria?** **No.**  

No open national Nigeria sinkhole event inventory was found. NGSA maps are geology, not sinkhole occurrences. Florida subsidence incident database is geography-wrong and largely unverified.  

**Honest conclusion:** **No public dataset adequately covers sinkhole + Lagos/Nigeria.**

**Institutional dataset that would satisfy:** Verified karst/collapse/sinkhole **incident inventory** (or absence maps) for Lagos or geologically analogous Nigerian carbonate/coastal settings from NGSA, state emergency agencies, insurers, or geotechnical firms — with verification status, coordinates, dates, and reuse rights. Modeled karst susceptibility alone is **not** sufficient as event ground truth.

### Flood (out of SSRI label set)

Public Nigeria flood extents exist (UNOSAT/HDX) but **do not unblock A1** for SSRI three classes. Do not treat flood extent as a substitute label for subsidence/landslide/sinkhole.

---

## Lagos InSAR qualification (DOI 10.7294/19738957) — 2026-09-08

**Scope:** Scientific-data qualification against SSRI repository contracts. **No download into training**, no synthetic labels, no A1 unblock declaration.

### Fact classification key

| Tag | Meaning |
|-----|---------|
| **Verified (repo)** | From SSRI source / docs in this repo |
| **External source** | From dataset deposit page, accompanying paper, or PMC full text |
| **Unresolved** | Not confirmed without file inspection or legal counsel |

### SSRI contract constraints applied (Verified (repo))

| Contract | Source | Requirement |
|----------|--------|-------------|
| Hazard classes | ml/labels.py | subsidence=0, landslide=1, sinkhole=2 |
| Label raster | ml/dataset.py, Stage 2.5 | label.tif; valid pixels {0,1,2} or 1-based; LABEL_NODATA=-1 |
| Features | CHANNEL_NAMES / CHANNEL_ORDER | **13 channels**; **no InSAR/VLM** |
| Grid | uild_feature_stack / GridSpec | Default **30 m**; CRS = UTM from AOI centroid (e.g. Lagos -> EPSG:32631) |
| Splits | DEFAULT_SPLIT | 70/15/15 train/val/test |
| Metrics path | evaluation/evaluator.py, 	raining/metrics.py | Masked P/R/F1/IoU + confusion; ROC helpers exist but unused in main path |
| Scientific status | scientific/report.py, Stage 2.9 | Automated audits != geological validity; SCIENTIFICALLY_VALIDATED requires human review |
| Current status | docs/production_qualification.md section 18 | SCIENTIFIC_VALIDATION=NOT VERIFIED |

### Dataset identity (External source)

| # | Item | Finding |
|---|------|---------|
| 1 | **Title** | Data for Land Subsidence Hazard and Building Collapse Risk in the Coastal City of Lagos, West Africa (v2; v1 title variant uses Hotspot) |
| 2 | **Authors / providers** | Leonard / Osadebamwen Ohenhen; Manoochehr Shirzaei (Virginia Tech). Publisher: University Libraries, Virginia Tech / Figshare |
| 3 | **Geographic coverage** | Lagos, Nigeria |
| 4 | **Temporal coverage** | Sentinel-1 ascending ~2018-03-18 to 2021-10-28; descending ~2018-03-13 to 2021-10-23. Risk scenarios: 4 / 10 / 35 / 75 yr under linear-rate assumption. Collapse catalog: compiled historical incidents (paper: 1978-2022 meta; 43 geolocated 2000-2022 in analysis) |
| 5 | **Spatial resolution** | Paper: adjacent InSAR pixels ~75 m apart for angular distortion; risk maps 0.2 x 0.2 km. DEM in processing: 30 m SRTM. **Not** a native SSRI 30 m hazard-label grid |
| 6 | **Native formats** | v1: InSAR_data.csv, LagosRiskMap.tif, BuildingCollapseTable.xlsx. v2: 12 files (VLM CSV; 4 risk GeoTIFFs + 4 risk CSVs; lon/lat CSVs; collapse XLSX) |
| 7 | **CRS** | VLM CSV: lon/lat degrees (WGS84 assumed). Risk GeoTIFF CRS: **Unresolved** without GeoTIFF tags |
| 8-9 | **Value semantics** | **Not** SSRI categorical hazard labels. (a) VLM CSV: **observed deformation rates** (cm/yr vertical + east-west). (b) Risk rasters: **building-collapse risk** R0-R4 from angular distortion x building density. (c) Collapse table: multi-causal **building failures**, not sinkhole inventory |
| 10 | **Ground truth / events** | Partial: ~106 collapse rows; 43 geolocated in paper. Structural failures != verified geological subsidence pixels. GNSS check limited |
| 11-13 | **License / reuse** | **Dataset v1:** **CC0 1.0** (External source, deposit page). **Paper:** **CC BY-NC 4.0**. **v2 license:** reconfirm (**Unresolved**). Legal counsel for commercial derived products |
| 14 | **Legal grid transform** | Under CC0 (v1), projecting VLM to SSRI UTM 30 m is legally plausible; confirm v2 |
| 15 | **Appropriate roles** | Benchmark / external observational reference; qualitative viz; **not** drop-in training or formal label.tif validation |

### Spatial compatibility

VLM lon/lat **can be projected** onto SSRI GridSpec (30 m UTM) with aggregation. Risk at 200 m can be resampled to 30 m only as **representation** — resampling **does not invent** native detail. Defensible for comparison maps; not equivalent to native 30 m geological labels.

### Label compatibility

Cannot defensibly supply {0,1,2} rasters as-is. Continuous VLM != binary subsidence. Binaryizing requires a **pre-declared protocol** (not done). Risk R0-R4 confounds hazard with **building density**. Collapse points are sparse external markers only.

### Temporal compatibility

Single ~2018-2021 VLM rate field -> **static spatial comparison**; not multi-epoch held-out temporal CV. Future risk horizons are **scenario extrapolations**. Collapse catalog supports sparse historical co-location only.

### Leakage analysis

| Risk | Assessment |
|------|------------|
| FeatureStack contains InSAR? | **No** (Verified (repo)) |
| Direct leakage if VLM stays external | **None** |
| VLM as feature + label | **High — forbidden** |
| Risk labels + urban spectral features | Indirect confounding |
| SRTM in authors pipeline vs SSRI COP30 | Related DEM family; document provenance; not automatic leakage |

### Hard role classification

**BENCHMARK-ONLY**

- Not TRAINING-SUITABLE: no label.tif match; inventing binary labels forbidden here.
- Not formal VALIDATION-SUITABLE: Stage 2.6/2.9 evaluator needs {0,1,2} labels + curated splits.
- Not NOT-SUITABLE: useful independent Lagos VLM reference for benchmarking subsidence scores.
- **A1 remains blocked** for a production three-head checkpoint.

---

## Recommendations (for human decision — not an auto-next step)

1. **Do not declare A1 unblocked.**
2. **Lagos InSAR (10.7294/19738957):** **BENCHMARK-ONLY** — optional later read-only benchmark harness (separate approval); **do not** train or silently binaryize.
3. **Landslide:** PUBLIC_LAGOS_DATA_NOT_FOUND — institutional inventories required.
4. **Sinkhole:** PUBLIC_LAGOS_DATA_NOT_FOUND — institutional inventories required.
5. Do **not** fill the matrix with flood or global COOLR as Lagos substitutes.

---

## Production training readiness (2026-09-08 repo audit)

### Hard determination

```text
TRAINING_BLOCKED
PRODUCTION_CHECKPOINT=BLOCKED
SCIENTIFIC_VALIDATION=NOT VERIFIED
```

**Reason:** No genuine SSRI `label.tif` / three-class (or approved single-class) labelled Lagos training dataset is present under `data/` or elsewhere in the repository. On-disk `data/` contains only geophysics feature rasters (WGM2012, EMAG2v3). Synthetic/e2e fixtures must not be promoted.

### In-repo evidence table (datasets actually found)

| Dataset | Hazard | Geography | Real labels? | Resolution | License | Training suitable? |
|---------|--------|-----------|--------------|------------|---------|-------------------|
| `data/geophysics` WGM2012 Bouguer | (feature: gravity) | Lagos clip | **No** (not hazard labels) | ~2′ native → 30 m resample | See provenance JSON | **Features only** |
| `data/geophysics` EMAG2v3 UC4km | (feature: magnetics) | Lagos clip | **No** | ~2′ → 30 m | See provenance JSON | **Features only** |
| Synthetic test fixtures (`model/tests`, e2e `checkpoint.pt`) | all three (synthetic) | n/a | **No** — fixture/synthetic | tile-sized | Internal | **No** — fixture only |
| Lagos InSAR DOI `10.7294/19738957` | subsidence **reference** (VLM/risk) | Lagos | **Not SSRI labels** | VLM ~75 m; risk 0.2 km | Deposit v1 CC0; paper CC BY-NC | **BENCHMARK-ONLY** |
| Global landslide catalogs (NASA COOLR/GLC) | landslide | Global (sparse Africa) | Event points (not Lagos raster labels) | point | Public catalogs | **No** as Lagos GT |
| Florida sinkhole/subsidence incidents | sinkhole-like | Florida, USA | Incident reports | point | Public | **No** — wrong geography |
| UNOSAT/HDX flood extents | flood | Nigeria | Flood water | event | Often CC BY-SA | **No** — not SSRI class |

### Partial-class research

Repository `SSRIModel` / Evaluator / scientific audits assume **three** classes `{0,1,2}` with warnings when a class is absent. There is **no** approved in-repo protocol to train a production three-head checkpoint from a single hazard inventory, nor to declare partial-class research scientifically validated. Any such experiment would require an explicit human scientific decision **before** training.

### Minimum institutional label packages required

**Landslide (and similarly sinkhole):** event location or polygon; event date; source/provenance; classification; CRS; spatial accuracy statement; reuse rights; completeness/coverage notes — dense enough for ~30 m UTM alignment or blocked spatial CV.

**Subsidence:** prefer independent geological/engineering labels. Optional future VLM→label protocol (thresholds, building-risk exclusion rules, expert review) is **not** implemented and **not** authorized here.

### External data-acquisition specification (precise request)

For each class, packages must align to SSRI `label.tif` with IDs **0=subsidence, 1=landslide, 2=sinkhole**, `LABEL_NODATA=-1`, target **~30 m** UTM (Lagos → EPSG:32631), and **not** include flood.

#### Subsidence (class 0)

| Requirement | Spec |
|-------------|------|
| Geometry | Polygons preferred; dense verified points acceptable if expandable to pixels |
| Attributes | hazard_class=`subsidence`; event_id; observation/interpretation date; method (field / InSAR-assisted **only if protocol approved**); confidence/verification status |
| Event/date | Observation window or event date ISO-8601 |
| Spatial accuracy | ≤30 m preferred; document if coarser |
| CRS | WGS84 or UTM with EPSG code |
| Coverage | Lagos State or declared coastal AOI with extent metadata |
| Labeling rules | Mutually exclusive vs landslide/sinkhole per pixel; no silent VLM thresholding without signed protocol |
| License | Research + preferably commercial reuse; record SPDX/terms |
| Metadata | source institution, contact, version, hash of delivered files |
| Acceptable sources | LASBCA / Lagos State Ministry of Physical Planning; geotechnical firms; NGSA (if event maps); peer-reviewed inventories with redistribution rights |
| Validation | Independent review subset; confusion vs BENCHMARK-ONLY InSAR allowed as **external** check only |

#### Landslide (class 1)

| Requirement | Spec |
|-------------|------|
| Geometry | Failure scarp/deposit **polygons** preferred; verified points with accuracy statement |
| Attributes | hazard_class=`landslide`; event_id; event_date; trigger if known; verification (field/photo/remote) |
| Event/date | Required; multi-date inventories must support temporal split rules |
| Spatial accuracy | ≤30–50 m; document |
| CRS | EPSG-coded |
| Coverage | Lagos State / SW Nigeria coastal-deltaic terrain comparable to FeatureStack AOIs |
| Labeling rules | Slope failure / mass movement only — not flood or erosion alone |
| License | Explicit reuse for ML training |
| Metadata | completeness notes (known under-reporting) |
| Acceptable sources | State emergency management; university/NGSA landslide inventories; partner GIS with MOU |
| Validation | Held-out spatial blocks; no COOLR/GLC global points as Lagos GT |

#### Sinkhole (class 2)

| Requirement | Spec |
|-------------|------|
| Geometry | Collapse/subsidence-sinkhole footprints or verified incident points |
| Attributes | hazard_class=`sinkhole`; event_id; date; verification status; genetic type if known (cover-collapse vs piping) |
| Event/date | Required |
| Spatial accuracy | ≤30–50 m |
| CRS | EPSG-coded |
| Coverage | Lagos / analogous Nigerian coastal or carbonate settings as declared |
| Labeling rules | Distinct from broad “subsidence”; karst susceptibility alone is **not** event GT |
| License | Explicit ML training reuse |
| Metadata | reporting bias notes |
| Acceptable sources | State agencies, insurers (anonymized), NGSA, geotechnical partners — **not** Florida FGS as Lagos GT |
| Validation | Expert review; spatial CV |

### Data-acquisition checklist (unblock TRAINING_READY)

1. Obtain licensed institutional polygons/points for **landslide** and **sinkhole** covering Lagos (or approved analogous AOI).
2. Decide subsidence ground truth: engineering inventory **or** separately approved InSAR protocol (keep deposit BENCHMARK-ONLY until then).
3. Build SSRI samples via `DatasetBuilder` + `LocalRasterLabelProvider`: `feature_stack.npy`, `label.tif` (`{0,1,2}` / nodata `-1`), `metadata.json`.
4. Freeze immutable `manifest.json` + `statistics.json` with hashes, CRS, resolution, extent, class counts, license.
5. Run Stage 2.9 audits + spatial/leakage checks; **stop** if leakage fails.
6. Train with `Trainer`/`TrainingConfig`; evaluate with `Evaluator` on held-out **test**; calibrate domain centroid from train embeddings.
7. Only then designate checkpoint production-trained (`is_fixture_checkpoint=false`) and re-run live Lagos assess **without** `SSRI_ALLOW_FIXTURE_CHECKPOINTS`.

---

## Concrete next scientific-validation plan (repo-aligned)

Goal: move from SCIENTIFIC_VALIDATION=NOT VERIFIED toward a **defensible** result — **do not invent metric values**.

1. **Datasets:** Institutional landslide + sinkhole labels; keep InSAR as benchmark reference unless a separate protocol is approved. Package SSRI samples: eature_stack.npy + label.tif + metadata.json + manifest.
2. **Labeling protocol:** Freeze definitions/verification before any metrics; forbid post-hoc threshold tuning.
3. **Spatial alignment:** 30 m UTM FeatureStack; nearest resample for categorical labels; document native vs target resolution.
4. **Splits:** Spatial blocking + alidate_spatial_splits / leakage checks; 70/15/15 only if AOI count supports it.
5. **Leakage controls:** Keep InSAR out of FeatureStack; Stage 2.9 audits.
6. **Metrics (when real labels exist):** Masked P/R/F1/IoU, confusion (Evaluator); optional ROC via calibration helpers — PENDING until run; MC CIs only with dropout>0; separate pre-registered VLM<->score agreement for benchmark track.
7. **Reproducibility:** Fingerprints, seeds, evaluation JSON/MD.
8. **Human gate:** SCIENTIFICALLY_VALIDATED only via accepted scientific review (ttach_review).

---

## Explicit non-claims

- No production training recommended from this qualification alone.
- No dataset ingested into model/ training paths.
- A1 / A2 / DoD #4 **not unblocked**.
- **Scientific validation has not succeeded** merely because the Lagos InSAR deposit exists.

---

## Sources consulted (selected)

- Repo: ml/labels.py, constants.py, dataset.py, scientific/*, evaluation/*, Stage 2.5-2.9 docs
- https://doi.org/10.7294/19738957 (v1 page: CC0 1.0)
- https://doi.org/10.1029/2022EF003219 ; PMC PMC10078203 (paper CC BY-NC 4.0)
- https://doi.org/10.7294/25864435
- NASA COOLR / GLC; ThinkHazard NGA LS; NGSA maps; FGS Florida; HDX/UNOSAT flood; Floodgate; Zenodo Nigeria atlas
