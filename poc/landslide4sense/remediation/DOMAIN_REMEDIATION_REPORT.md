# DeepSlide Input-Domain Remediation Experiment

**Verdict: PASS** (technical domain remediation)  
**Scientific validation: UNRESOLVED**  
**Production integration: NOT authorized** (separate gate; still blocked on SSRI 13-ch contract and labelled georef eval)

## Root cause

The empty georeferenced maps were caused by a **value-domain mismatch**, not a broken checkpoint.

| Path | What was fed to DeepSlide | Result @ thr=0.5 |
|------|---------------------------|------------------|
| Prior STAC ingest | Reflectance ≈0–1, DEM meters, slope degrees (**no packaging**) | Empty (max score ≈0.01–0.23) |
| Competition HDF5 | Packaged tensors DeepSlide was trained on | Non-empty (held-out micro F1 ≈0.53) |

DeepSlide config (`normalize: False`) expects the **already packaged** Landslide4Sense tensors, not physical STAC units.

## Authoritative preprocessing evidence

IARAI contributor **YonghaoXu** ([issue #4 comment](https://github.com/iarai/Landslide4Sense-2022/issues/4#issuecomment-1195457420)):

> The 14 bands of the data are simply divided by a mean vector to implement the normalization:
>
> `img_mean = [1111.81236406, 824.63171476, 663.41636217, 445.17289745, 645.8582926, 1547.73508126, 1960.44401001, 1941.32229668, 674.07572865, 9.04787384, 1113.98338755, 519.90397929, 20.29228266, 772.83144788]`

**Defensible recipe used here**

1. Build raw stack at ~10 m: Sentinel-2 bands in **scaled reflectance DN** (≈0–10000; if STAC gives 0–1, multiply by 10000), slope in **degrees**, DEM in **meters**.
2. Package: `packaged[c] = raw[c] / img_mean[c]` for c=1…14.
3. Infer with DeepSlide: NaN→0/ε, **no** extra mean/std, sigmoid, threshold **0.5** (not lowered).

Verification: multiplying validation HDF5 chips by `img_mean` recovers optical DN-scale, slope≈degrees, DEM≈meters — consistent with the contributor statement. See `outputs/packaging_verification.json`.

Band order unchanged: S2 B1–B12 (B8A omitted), slope, DEM.

## Before / after distributions (selected)

Full tables: `outputs/distribution_compare.csv`, `outputs/DOMAIN_REMEDIATION_REPORT.json`.

Prior mistaken STAC path kept optical in ~0–1 while L4S packaged optical means are typically O(1) after ÷mean. DEM/slope were left in meters/degrees instead of ÷772.8 / ÷20.3.

## Controlled diagnostics (fixed thr=0.5)

AOI: Iburi-region window `[141.85, 42.70, 141.90, 42.74]`, CRS `EPSG:32654`, 128×128 @ 10 m.

| Experiment | max score | pred_pos | empty? |
|------------|-----------|----------|--------|
| BEFORE: reflectance/10000, no ÷mean | 0.231 | 0 | yes |
| CONTROL: reflectance/10000 then ÷mean (wrong optical scale) | 0.002 | 0 | yes |
| AFTER: DN-scale then ÷img_mean | **0.999** | **7777** | **no** |
| Sanity: L4S val `image_10.h5` | 0.998 | 691 | no |

Optical scale isolation: ÷mean alone is not enough if reflectance stays in 0–1; DN restoration (×10000) is required for optical bands.

## Georeferenced artifacts

| File | Notes |
|------|-------|
| `outputs/prediction_georef_after.tif` | CRS + affine preserved; band1 mask, band2 uncalibrated score |
| `outputs/prediction_georef_before.tif` | Empty baseline |
| `outputs/preview_before_after.png` | Visual before/after |
| `outputs/stac_raw_14chw.npy` / `stac_packaged_after.npy` | Intermediate stacks |

## Evaluation vs baselines

- **Labelled held-out:** prior L4S validation chips 1–40 (already packaged): micro F1 **0.529** vs majority 0 / slope 0.033 — unchanged by this packaging (chips were already correct).
- **This AOI:** no pixel inventory labels → **cannot** claim geographic held-out metrics here.
- Positive fraction on Iburi window ≈ **47%** — spatially coherent but **not** inventory-validated; may include residual DEM/sensor mismatch (Copernicus vs ALOS) and scene bias. Not “empty,” not all-positive, but **not** a scientific pass.

## Runtime

- Model load ≈ 4.4 s (CPU)
- Infer ≈ 0.047 s / 128×128 chip

## Fine-tuning assessment

Not required for this technical remediation because packaging is now authoritative. Fine-tune remains optional for:

- Copernicus DEM vs ALOS PALSAR residual gap  
- L2A B10 zero-fill  
- Physical-unit training if packaging is undesirable long-term  

Adequate free **labelled + georeferenced + 14-band** fine-tune data was not assembled in this experiment (L4S labels lack CRS; Bijie is RGB+DEM).

## Limitations (explicit)

- Uncalibrated sigmoid ≠ landslide risk  
- No pixel GT on the georeferenced AOI  
- DEM sensor differs from L4S (Copernicus vs ALOS)  
- B10 zeros on L2A  
- Does not fix SSRI’s 13-channel assess contract  
- Does **not** by itself authorize `/api/v1/assess` integration

## Final verdict

| Question | Answer |
|----------|--------|
| Root cause identified? | **Yes** — missing ÷`img_mean` packaging (+ optical DN scale) |
| Transform documented & defensible? | **Yes** — IARAI contributor recipe |
| Non-empty georef mask @ 0.5? | **Yes** |
| CRS/transform preserved? | **Yes** (`EPSG:32654`) |
| Scientific validation? | **UNRESOLVED** |
| Experiment verdict | **PASS** (domain remediation) |
| Wire into production SSRI? | **No** — still need labelled georef eval + 14-band SSRI ingest design |

### Commands

```powershell
poetry -C model run python ../poc/landslide4sense/remediation/compare_distributions.py
poetry -C model run python ../poc/landslide4sense/remediation/run_domain_remediation.py
```
