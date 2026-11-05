# Landslide4Sense isolated PoC

Landslide-only proof that a **pretrained** geospatial segmentation model can produce real pixel predictions on Landslide4Sense chips. Does **not** modify SSRI production code.

## Verdict

See `outputs/EXECUTION_REPORT.md` and `outputs/execution_report.json`.

## What ran

| Item | Detail |
|------|--------|
| Primary candidate | IARAI baseline U-Net `batch3500_F1_7396.pth` |
| Primary status | **BLOCKED** — `cloud.iarai.ac.at` DNS NXDOMAIN |
| Executed model | DeepSlide MobileNetV2 U-Net (`smp.Unet`), MIT |
| Checkpoint | `weights/mobilenetv2.pth` from [harshinde/DeepSlide_Models](https://huggingface.co/harshinde/DeepSlide_Models) (~25.6 MB) |
| Data | Landslide4Sense train chips (`data/images`, `data/masks`), 14×128×128 HDF5, ~10 m/px claimed |
| Georeference | **Not available** in source chips; local-grid GeoTIFF only |

## Commands

```powershell
# from repo root
poetry -C model run pip install h5py segmentation-models-pytorch
# weights (already present if PoC was run):
# curl.exe -L -o poc/landslide4sense/weights/mobilenetv2.pth `
#   https://huggingface.co/harshinde/DeepSlide_Models/resolve/main/mobilenetv2.pth
poetry -C model run python ../poc/landslide4sense/run_poc.py
```

## SSRI stack note

SSRI Stage 2.5 uses a **13-channel** feature stack. This PoC uses the **14-band** Landslide4Sense layout (S2 B1–B12 + slope + DEM). There is no scientifically defensible remap of the existing SSRI stack into L4S without rebuilding inputs.

## Outputs

- `outputs/preview_map.png` — RGB / GT / probability / overlay
- `outputs/pred_mask_*.h5` — binary masks + probability
- `outputs/prediction_local_grid.tif` — synthetic local 10 m grid (**no real CRS**)
- `outputs/EXECUTION_REPORT.md` — human report
