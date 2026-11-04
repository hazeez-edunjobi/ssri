# DeepSlide Final Production Readiness

**Executive verdict: FAIL**

DeepSlide is **not** approved as SSRI’s permanent production landslide engine.  
An independent CONUS evaluation corpus was built and run; DeepSlide **failed** predeclared Gate A acceptance criteria.  
Production `/api/v1/assess` was **not** modified. No deployment was performed.

Generated from executed Gates A–C under `poc/landslide4sense/`.

---

## Gate summary

| Gate | Result | Meaning |
|------|--------|---------|
| **A** Independent geographic scientific validation | **FAIL** | USGS+STAC 14-band eval set built (24 chips, 3 spatial blocks); chip F1 **0.091** — beats majority, loses to slope baseline, below 0.40 floor |
| **B** SSRI integration design / contract compatibility | **PASS** | Isolated landslide-only engine + GeoTIFF prototype; existing 13-ch assess untouched |
| **C** Deployment feasibility | **PASS (local only)** | CPU load/infer/memory OK locally; **live Render not tested** |

**Approval rule:** all three must pass → **not met** → **FAIL** (independent eval completed; model underperforms acceptance gates).

---

## 1. Exact model integrity

| Field | Value |
|-------|-------|
| Architecture | `smp.Unet(encoder_name=mobilenet_v2, in_channels=14, classes=1)` |
| Checkpoint | `poc/landslide4sense/weights/mobilenetv2.pth` |
| SHA-256 | `a743e627dd68a1409ddda4ad43b70b53ee92c0d504d16c890e128ba04dc9ab4f` (matches HF LFS) |
| License | MIT (DeepSlide model card) |
| Threshold | **0.5** (fixed; not tuned on the Gate A set) |
| Preprocess version | `l4s-pack-v1-div-img-mean` |
| Packaging | `raw[c] / img_mean[c]` ([IARAI issue #4](https://github.com/iarai/Landslide4Sense-2022/issues/4#issuecomment-1195457420)) |
| Output semantics | Uncalibrated sigmoid segmentation score — **not** calibrated probability, **not** validated risk |

Evidence: `validation/outputs/phase1_model.json`, `remediation/outputs/packaging_verification.json`, `integration/deepslide_engine.py`.

---

## 2. Gate A — Independent geographic scientific validation

**Result: FAIL** (dataset constructed; metrics fail acceptance)

### Requirement
Georeferenced landslide / non-landslide labels + Sentinel-2 B1–B12 + slope + DEM (or defensible construction), geography **independent** of Landslide4Sense study areas (Iburi, Kodagu, Gorkha, Taiwan), with spatial-block splits.

### Construction (executed)

| Field | Value |
|-------|-------|
| Inventory | USGS Landslide Inventories v3 (CONUS points) |
| Absences | Same 5° geographic block as presence (catalog pseudo-absences) |
| Stacks | Planetary Computer STAC S2 L2A + Copernicus DEM → 14 bands |
| Labels | 40 m buffer around inventory points; all-zero absence masks |
| Split | Evaluation-only 5° blocks: `35_-125`, `35_-80`, `35_-85` |
| N | 24 chips (12 / 12), prevalence 0.5 |
| Threshold | 0.5 fixed |

Artifacts: `production_gates/gate_a_build/` (`GATE_A_BUILD_REPORT.md`, `INVENTORY_CANDIDATES.md`, `REPRODUCE.md`, `outputs/gate_a_eval_report.json`).

### Chip-level metrics (primary)

| Method | F1 | Notes |
|--------|-----|-------|
| DeepSlide | **0.091** | P=0.10, R=0.083; TP=1 FP=9 FN=11 TN=3 |
| Majority (always negative) | 0.0 | |
| Slope mean > 15° | **0.375** | Stronger than DeepSlide on this set |

Acceptance: beat majority ✓ · beat slope ✗ · min F1 ≥ 0.40 ✗ → **FAIL**.

### Candidates reviewed (earlier discovery + build)

| Dataset | Outcome |
|---------|---------|
| L4S validation HDF5 | Reject — no CRS; not geo-independent |
| `usgs_landslide_featurestacks/v3` | Reject as-is — 13-ch SSRI; **points reused** |
| Hokkaido/Iburi | Reject — L4S study area |
| Nepal Zenodo scars | Reject — RGB only |
| Sen12Landslides | Reject — incomplete L4S bands / size |
| USGS v3 + STAC | **Built** — used for this evaluation |

### Explicit non-claims
- L4S chip micro-F1 **0.529** is competition held-out, not this independent CONUS result.
- Non-empty / spatially coherent maps are **not** scientific validation.
- Beating majority alone is **not** acceptance (slope gate failed).
- Point-buffer labels remain weaker than scar polygons; even a numeric PASS would not equal full scar-level validation.

### Copernicus DEM / B10
Documented residuals: Copernicus DEM (not ALOS); L2A B10 zero-filled. Flagged per chip in metadata.

---

## 3. Gate B — Integration design and contract compatibility

**Result: PASS** (isolated prototype only)

| Contract | Assess / Stage 2.5 | DeepSlide |
|----------|--------------------|-----------|
| Channels | **13** (`CHANNEL_NAMES`) | **14** (B01–B12, slope, DEM) |
| Endpoint | `POST /api/v1/assess` | **Not connected** |
| Hazards | subsidence, landslide, sinkhole | **landslide only** |

Isolated engine: `integration/deepslide_engine.py`  
Prototype GeoTIFF: `production_gates/outputs/gate_b_prototype_prediction.tif`  
Results JSON: `production_gates/outputs/gate_b_c_results.json`

---

## 4. Gate C — Deployment feasibility

**Result: PASS (local only)** — live host **not** verified

| Metric | Local CPU |
|--------|-----------|
| Engine init | ~4–5 s |
| Infer / 128×128 | ~0.04–0.05 s |
| Peak RSS | ~427 MB |
| GPU | Not required |
| Live `ssri-api.onrender.com` | **Not tested** |

Evidence: `production_gates/outputs/gate_b_c_results.json`, prior `validation/outputs/deployment_measure.json`.

---

## 5. Automated tests

```text
poetry -C model run pytest poc/landslide4sense/integration/test_deepslide_engine.py -q
→ 9 passed
```

Log: `production_gates/outputs/pytest_stdout.txt`.

---

## 6. Remaining limitations

1. **Gate A FAIL** — independent CONUS eval does not support production approval.
2. SSRI assess still 13-channel; DeepSlide needs a separate path if ever revisited.
3. Uncalibrated scores ≠ risk.
4. Copernicus DEM / B10 zero-fill residuals vs ALOS L4S training.
5. Live Render memory/cold-start unverified.
6. Landslide only — no subsidence/sinkhole claim.
7. Point-buffer labels are approximate vs scar polygons.

---

## 7. Minimum actions after FAIL

1. Do **not** integrate DeepSlide into production assess.
2. If landslide ML is still required: either improve domain transfer / retrain under an approved plan with scar-quality labels, or select a different approach — **out of scope for this gate**.
3. Optional: expand the USGS+STAC corpus with polygon inventories for stronger labels; that would re-test the model, not excuse the current FAIL.

---

## Evidence index

| Artifact | Path |
|----------|------|
| This report | `poc/landslide4sense/FINAL_PRODUCTION_READINESS.md` |
| Gate A discovery (pre-build) | `production_gates/outputs/gate_a_discovery.json` |
| Gate A build + eval | `production_gates/gate_a_build/` |
| Gate A eval JSON | `production_gates/gate_a_build/outputs/gate_a_eval_report.json` |
| Gate B/C results | `production_gates/outputs/gate_b_c_results.json` |
| Pytest log | `production_gates/outputs/pytest_stdout.txt` |
| Engine + tests | `integration/deepslide_engine.py`, `integration/test_deepslide_engine.py` |
| Domain remediation | `remediation/DOMAIN_REMEDIATION_REPORT.md` |
| Prior release gate | `RELEASE_READINESS.md` |
| L4S held-out metrics | `validation/outputs/heldout_eval.json` |

**Final decision: FAIL — do not adopt DeepSlide as production landslide engine.**
