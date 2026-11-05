# Landslide4Sense PoC — Execution Report

**Verdict: PASS** (DeepSlide fallback). Official IARAI baseline weights remain **BLOCKED** (DNS).

Successful execution alone does not establish scientific validity. Landslide only — no subsidence/sinkhole claim.

## Phase 1 — Repository inspection (SSRI)

| Item | Finding |
|------|---------|
| Assess model | Stage 2.5 `SSRIModel` U-Net, input `(B, 13, H, W)` |
| Channels | `elevation, slope, plan_curvature, profile_curvature, twi, relative_relief, valley_depth, ndvi, ndwi, clay_mineral_ratio, iron_oxide_index, gravity, magnetics` |
| Labels | `subsidence=0, landslide=1, sinkhole=2`, nodata `-1` |
| Checkpoints in repo | Foundation multitask `ssri-foundation-v*.pt` (not assess-loadable); no L4S weights |
| L4S required input | 14 bands: S2 B1–B12 + ALOS slope + DEM, 128×128 @ ~10 m/px |
| SSRI→L4S transform | **Not scientifically defensible** without rebuilding S2+DEM/slope stacks |
| Env | Poetry `model/` env: torch 2.15 CPU, enough RAM for ~6.6M-param MobileNetV2; `h5py` + `segmentation-models-pytorch` installed for PoC only |

## Model tested

1. **Primary (BLOCKED):** IARAI Landslide4Sense baseline U-Net  
   - Checkpoint: `batch3500_F1_7396.pth`  
   - Source: `https://cloud.iarai.ac.at/index.php/s/CgbjDRK6B5KYaLE`  
   - Code: MIT (`iarai/Landslide4Sense-2022`); data CC-BY-4.0  
   - Blocker: DNS **NXDOMAIN** for `cloud.iarai.ac.at` / `nextcloud.iarai.ac.at`

2. **Executed (PASS):** DeepSlide MobileNetV2 U-Net  
   - Checkpoint: `poc/landslide4sense/weights/mobilenetv2.pth` (25.57 MB)  
   - Source: [harshinde/DeepSlide_Models](https://huggingface.co/harshinde/DeepSlide_Models) (MIT)  
   - Arch: `smp.Unet(encoder_name="mobilenet_v2", in_channels=14, classes=1)`  
   - Paper-reported F1 on L4S: 0.7119 (not revalidated here)

## Commands

```powershell
# from repo root
poetry -C model run pip install h5py segmentation-models-pytorch
curl.exe -L -o poc\landslide4sense\weights\mobilenetv2.pth `
  https://huggingface.co/harshinde/DeepSlide_Models/resolve/main/mobilenetv2.pth
# sample chips already under poc/landslide4sense/data/{images,masks}
poetry -C model run python ../poc/landslide4sense/run_poc.py
```

## Input dataset and preprocessing

- **Dataset:** Landslide4Sense train chips (HF mirror of competition HDF5)
- **Chips used:** images/masks `1, 2, 3, 5, 10, 20, 50, 100` downloaded; eval ids `1, 10, 100, 50`
- **Shape:** `(128, 128, 14)` in file → transposed to `(14, 128, 128)` for the model
- **Preprocess (DeepSlide):** NaN → `1e-6`; **no** mean/std normalize; sigmoid; threshold `0.5`
- **Official L4S baseline preprocess (not used here):** channel mean/std from `landslide_dataset.py`
- **CRS:** none in source HDF5

## Generated artifacts

| File | Description |
|------|-------------|
| `outputs/preview_map.png` | RGB / GT / probability / overlay for chip 1 |
| `outputs/pred_mask_*.h5` | Binary mask + probability |
| `outputs/pred_prob_*.npy` / `pred_mask_*.npy` | NumPy dumps |
| `outputs/prediction_local_grid.tif` | 2-band local 10 m grid (**CRS=None**, synthetic affine only) |
| `outputs/execution_report.json` | Machine-readable report |

## Evaluation (smoke only — not scientific validation)

Eval chips are from the **public train split** and may overlap DeepSlide training data.

### Micro-averaged (all eval pixels)

| Method | Precision | Recall | F1 | IoU |
|--------|-----------|--------|----|-----|
| DeepSlide MobileNetV2 | 0.5235 | 0.8039 | **0.6341** | 0.4643 |
| Majority (all non-LS) | 0.0000 | 0.0000 | 0.0000 | 0.0000 |
| Slope threshold | 0.0277 | 0.5739 | 0.0529 | 0.0272 |

- Outperforms majority baseline: **yes**
- Outperforms slope heuristic: **yes**
- Suitable for further investigation: **yes** (as a landslide-only research path with a new 14-band ingest)
- Suitable as production SSRI risk map: **no**

### Per-chip F1 (model)

| Chip | GT pos | Pred pos | F1 |
|------|--------|----------|-----|
| 1 | 405 | 504 | 0.675 |
| 10 | 0 | 0 | 0.000 (empty) |
| 100 | 479 | 799 | 0.659 |
| 50 | 29 | 99 | 0.094 |

## Runtime and resources

| Metric | Value |
|--------|-------|
| Device | CPU (torch 2.15.0+cpu) |
| Checkpoint size | 25.57 MB |
| Model params | ~6.6M |
| Build+load | ~17.5 s |
| Infer | ~0.10 s / 128×128 chip |
| Deps added for PoC | `h5py`, `segmentation-models-pytorch` (in poetry env; not production lockfile change) |
| Hosting fit | Fits typical Render/CPU free-tier memory for single-chip inference; GPU optional |

## Verdict and integration recommendation

**Verdict: PASS** for “pretrained landslide model produces real pixel predictions on L4S data.”

**Do not integrate into SSRI assess yet.**

Reasons:
1. Official IARAI weights still unreachable from this network.
2. SSRI’s 13-channel stack is incompatible with L4S/DeepSlide 14-band input.
3. Competition chips lack real CRS; SSRI map products need georeferenced STAC/COG stacks.
4. Results are landslide-detection smoke tests, not validated susceptibility products.

**Next candidate if continuing:** keep DeepSlide ResNet34 (~98 MB, higher reported F1) once a Sentinel-2 + DEM/slope pipeline exists; or retry IARAI `batch3500_F1_7396.pth` from a reachable mirror. Larger foundation models (Prithvi/TerraMind) only after that ingest exists.
