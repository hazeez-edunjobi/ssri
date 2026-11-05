# SSRI DeepSlide Landslide — Release Readiness Report

**Overall verdict: BLOCKED**  
**Integration authorized: NO** (not performed)

Generated: 2026-11-03T18:12:03.655107+00:00

## 1. Exact model and checkpoint

| Field | Value |
|-------|-------|
| Model | DeepSlide MobileNetV2 U-Net (`smp.Unet`, 14→1) |
| Checkpoint | `poc/landslide4sense/weights/mobilenetv2.pth` |
| SHA256 | `a743e627dd68a1409ddda4ad43b70b53ee92c0d504d16c890e128ba04dc9ab4f` |
| HF LFS match | True |
| License | MIT |
| Source | [harshinde/DeepSlide_Models](https://huggingface.co/harshinde/DeepSlide_Models) |
| Preprocess | NaN→ε; **normalize=False**; sigmoid; threshold **0.5** (DeepSlide default; not tuned on eval) |

## 2. Real geographic inference

| Check | Result |
|-------|--------|
| STAC 14-band stack with CRS | Built (`EPSG:32653`) |
| Domain-matched to DeepSlide training | **NO** (physical units vs L4S competition tensors) |
| Prediction GeoTIFF with real CRS | Written: `validation/outputs/georef/prediction_georef.tif` |
| Useful non-empty mask | **NO** — empty at 0.5 (max score ≈ 0.011) |
| Calibrated risk | **NO** — uncalibrated segmentation score |

## 3. Held-out evaluation

- **Dataset:** Landslide4Sense **validation** chips 1–40 (HF), 655 360 pixels, landslide prevalence ≈ 1.14%
- **Split:** competition validation (held-out from train); not a spatial-block split of an independent inventory
- **Threshold:** fixed 0.5 (author default), declared before eval in `acceptance_criteria.json`

| Method | Precision | Recall | F1 | IoU |
|--------|-----------|--------|----|-----|
| DeepSlide | 0.4876 | 0.5787 | **0.5292** | 0.3598 |
| Majority | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Slope heuristic | 0.0172 | 0.5285 | 0.0334 | 0.0170 |

Confusion (model): TN=643299, FP=4561, FN=3160, TP=4340

Numeric gates (pre-declared): **PASS** (≥0.50 F1; beat majority; beat slope by ≥0.10).  
**Scientific acceptance: UNRESOLVED** (does not equal production validation).

## 4. Georeferenced map

CRS-aligned GeoTIFF + preview exist under `validation/outputs/georef/`, but they are **not** accepted as a production landslide map because the input domain is wrong and the mask is empty.

## 5. Deployment architecture

| Metric | Value |
|--------|-------|
| Load (CPU) | 4.785 s |
| Infer / chip | ~0.0452 s |
| Peak RSS | ~425 MB |
| Live Render verified | **NO** |
| Compatible with current `/api/v1/assess` 13-ch stack | **NO** |

Isolated CPU inference is light enough for typical small hosts; wiring into SSRI is not ready.

## 6. Remaining limitations

- Landslide only — no subsidence/sinkhole claim
- L4S competition chips have no CRS; cannot georeference them honestly
- Competition value scaling unpublished; STAC physical units ≠ training domain
- Held-out numeric pass on HF validation labels; scientific validation UNRESOLVED
- Sigmoid scores are uncalibrated — not risk probabilities
- Production Render live test not authorized/executed
- SSRI 13-channel assess path incompatible without new ingest

## 7. Gate checklist

| Criterion | Result |
|-----------|--------|
| phase1_model_authenticated | **PASS** |
| phase2_georeferenced_input_ok | **BLOCKED** |
| phase3_held_out_gates_pass | **PASS** |
| phase3_scientific_validation | **UNRESOLVED** |
| phase4_georeferenced_output_ok | **FAIL** |
| phase5_deployment_feasibility_ok | **FAIL** |
| ssri_input_contract_compatible_or_new_pipeline_ready | **FAIL** |

## Final decision

**BLOCKED** — Do **not** integrate DeepSlide into SSRI assess/worker.

### Smallest remediation plan
1. **Reproduce Landslide4Sense competition band scaling (or retrain/fine-tune DeepSlide on physically unit STAC stacks with spatial-block holdout).** — STAC georeferenced stacks are CRS-valid but domain-shifted; georef inference produced empty masks (max sigmoid≈0.01).
2. **Build SSRI 14-band ingest (S2 B1–B12 + DEM/slope) with CRS, replacing reliance on the 13-channel Stage 2.5 stack for landslide-only path.** — Assess/worker cannot feed DeepSlide without a new feature pipeline.
3. **Obtain ALOS PALSAR DEM/slope (or justify Copernicus DEM) and a real B10 source if required; keep B10 fill documented.** — L4S used ALOS PALSAR; STAC path used Copernicus GLO-30 and zero-filled B10.
4. **After domain-matched georef works, run labelled georeferenced AOI evaluation and a live Render memory/cold-start test with authorization.** — Phase 4 map usefulness and Phase 5 production verification remain open.
5. **Do not integrate behind /api/v1/assess until all PASS FOR INTEGRATION gates clear.** — Integration gate explicitly forbids partial pass.

### Artifacts
- `validation/acceptance_criteria.json` (pre-declared)
- `validation/outputs/phase1_model.json`
- `validation/outputs/heldout_eval.json`
- `validation/outputs/georef/georef_report.json`
- `validation/outputs/deployment_measure.json`
- `validation/outputs/RELEASE_READINESS.json`
