# SSRI — Subsidence Validation Report

**Date:** 2026-11-24  
**Checkpoint:** `ssri-model-e7af3afcd0`  
**SHA256:** `d912027e17ed532687f9d2a2c74fd3c18ca8c812ae49107d939ade19dde5d004` (verified unchanged)  
**Decision:** **NOT VALIDATED** · readiness **BLOCKED BY MISSING DATA**

---

## Existing model and checkpoint provenance

- Stage 2.5 `SSRIModel`, 13-channel live assess contract.
- Registry scientific status: **NOT_VALIDATED**.
- Dataset provenance: synthetic / local bootstrap (`SYNTHETIC-local-bootstrap`).
- Susceptibility scores are **relative rankings**, not calibrated probabilities.
- Abeokuta historical score (~58.2% subsidence point estimate) must **not** be read as a 58.2% probability of subsidence.

Active checkpoint and 13-channel schema were **not** modified.

---

## Available ground-truth datasets

Repository search (catalogue, `data/`, `poc/`, fixtures, docs) — including a dedicated inventory pass — found **no observation-backed Stage 2.5 subsidence labels**:

| Candidate | Nature | Usable for Stage 2.5 subsidence validation? |
|---|---|---|
| `data/catalogs/usgs_landslide_v3/` + featurestacks | **Real** USGS landslide inventory (CONUS) | **No** — landslide-only; manifest marks subsidence missing / masked |
| USGS pseudo-absence sampling audit | Methodological negatives for landslide | **No** — not field-confirmed; not subsidence controls |
| Abeokuta TMI sheet 260 / Lagos WGM–EMAG clips | **Real** geophysics | **No** — features only; not hazard labels |
| Stage 2.5 / release-shell synthetic ZIPs & fixtures | Synthetic | **No** |
| Demo / presentation assessments | Model outputs | **No** |
| `data/catalogs/uglc_africa/raw/` | Placeholder | **Empty** — not downloaded |
| Lagos InSAR (Ohenhen & Shirzaei; registry / docs) | Documented benchmark | **Not cached locally**; registry treats as VLM/benchmark-only, not `label.tif` |
| Borehole / groundwater / Nigerian subsidence inventory | Asked in client docs | **Absent on disk** |
| Curated real subsidence inventory for the live AOI | — | **Not present** |

Empty schema stub written to:

`data/outputs/validation/subsidence_ground_truth_schema.json`

Missing-data report:

`poc/subsidence_validation_missing_report.json`

Existing harnesses that can score a checkpoint **once** real `label.tif` / inventory rows exist: `ssri_model.evaluation.*` and `release_shell/evaluate.py` (plus the new `subsidence_validation` schema path).

---

## Dataset quality

No real inventory to score. Schema requires:

- `longitude`, `latitude`, `label` (1=observed subsidence, 0=validated control)
- `source`, `observed_date`
- Explicit CRS (default EPSG:4326)
- Forbidden: model scores, synthetic Stage 2.5 labels, TMI-as-subsidence

Minimum floors for non-exploratory metrics: ≥30 positives, ≥30 negatives, ≥3 spatial blocks.

---

## Validation methodology (implemented infrastructure)

Module: `ssri_model.evaluation.subsidence_validation`

- Ground-truth schema + stub writer  
- Inventory quality / duplicate XY checks  
- Geographic block IDs (default 0.5°) for leakage awareness  
- When real labels + scores exist: ROC-AUC, PR-AUC, precision, recall, F1, confusion matrix, Brier, reliability bins  
- Always keeps `scientific_validation_status=NOT_VALIDATED` until independent review  
- Refuses to invent metrics when ground truth is missing  

Tests: `model/tests/test_subsidence_validation.py` (pass).

---

## Spatial splitting strategy

Geographic blocks (`floor(lon/block_deg)`, `floor(lat/block_deg)`). Random neighbouring pixel splits are **not** used as the primary strategy (leakage risk).

---

## Metrics / calibration / uncertainty

**Not computed on real data** — blocked by missing ground truth.

Toy unit-test scores only prove the metric plumbing; they are explicitly labelled synthetic and do not change readiness.

Domain similarity / CI behaviour on live assess remains as previously documented (often uncalibrated / degenerate bands). No fabricated intervals were added.

---

## Missing evidence

Required before scientific validation:

1. Authoritative observed subsidence positives (agency GIS / peer-reviewed inventories) with licence and CRS.  
2. Validated non-subsidence controls in the same domain.  
3. Documented collection methodology and dates.  
4. Spatially independent evaluation design reviewed by a geoscientist.  
5. Optional: InSAR deformation hotspots **after** geological review (deformation ≠ automatic subsidence class).

Documented external paths (not ingested in this session): Figshare Lagos InSAR under an approved deformation→class-0 protocol; client settlement/borehole/InSAR with explicit definitions; national survey inventories (`docs/dataset_candidates_report.md`, `docs/AFRICAN_TARGET_DATA_STATUS.md`). Florida/other non-Nigeria sinkhole inventories remain wrong geography for Abeokuta validation.

---

## Scientific readiness decision

| Question | Answer |
|---|---|
| Does the model emit a subsidence score? | Yes (relative ranking) |
| Is it scientifically validated? | **No — NOT_VALIDATED** |
| Can validation run when data arrives? | **Yes** (schema + harness ready) |
| Blocking issue | **Missing real ground-truth inventory** |
