# Stage 2.7 — SSRI Inference & Geospatial Prediction Pipeline

This document describes the offline inference system that applies a trained SSRI
checkpoint to a Stage 1 feature stack and produces geospatial hazard predictions.

## Architecture

```
InferenceConfig
    │
    ▼
validate_inference_setup()  ── safety checks (paths, channels, stats, CRS)
    │
    ▼
load_inference_checkpoint() ── restore SSRIModel from checkpoint model_config
    │
    ▼
memmap feature_stack.npy    ── (13, H, W), no full-RAM load required
    │
    ▼
generate_windows()          ── tile_size / overlap window grid
    │
    ▼
for each window batch:
    read window → valid mask → normalize (statistics.json)
    model.forward (eval, no_grad) → softmax probabilities
    accumulate prob_sum / weight_sum (uniform overlap blending)
    │
    ▼
argmax + confidence + nodata contract
    │
    ▼
GeoTIFF outputs + inference.json
```

Modules live under `ssri_model.inference`:

| Module | Responsibility |
|--------|----------------|
| `config.py` | `InferenceConfig` |
| `exceptions.py` | Typed inference errors |
| `safety.py` | `validate_inference_setup()` |
| `checkpoint.py` | Checkpoint loading wrapper |
| `tiling.py` | Window generation and overlap weights |
| `runner.py` | `InferenceRunner`, `run_inference()` |
| `predictions.py` | GeoTIFF writers |
| `metadata.py` | Manifest parsing and `inference.json` |

## Public API

```python
from ssri_model.inference import (
    InferenceConfig,
    InferenceRunner,
    run_inference,
    validate_inference_setup,
)
```

## Tensor Contract

**Input:** `(C, H, W)` with `C = 13`, converted to `float32` before inference.

**Output:**

| Array | Shape | Dtype | Valid pixels | Invalid/nodata pixels |
|-------|-------|-------|--------------|------------------------|
| `prediction` | `(H, W)` | int64 | argmax class (0–2) | `-1` (`LABEL_NODATA`) |
| `probabilities` | `(3, H, W)` | float32 | softmax, sum ≈ 1 | `0` |
| `confidence` | `(H, W)` | float32 | max probability | `0` |
| `mask` | `(H, W)` | bool | all channels valid | `False` |

Class IDs: `0 = subsidence`, `1 = landslide`, `2 = sinkhole`.

## Normalization

Inference reuses Stage 2.2 normalization:

- Loads `statistics.json` via `load_feature_statistics()`
- Applies `NormalizationConfig` from manifest when present, otherwise canonical defaults
- Never refits statistics during inference
- Rejects missing channels, unknown channels, or incompatible configuration

## Nodata Behavior

- `FEATURE_NODATA = -9999.0` marks invalid feature pixels
- A pixel is valid only when **all 13 channels** are not nodata
- Invalid feature values are zeroed after normalization and must not influence outputs
- `-9999` is never passed to convolution layers

## Windowed Inference

Large AOIs are processed through overlapping windows without loading the full stack into RAM:

- Feature stack opened with `numpy.load(..., mmap_mode="r")`
- Default settings: `tile_size=512`, `overlap=64`, `batch_size=4`
- Edge windows smaller than `tile_size` are zero-padded for batched inference
- Full-grid valid mask computed in row chunks

## Overlap Strategy

Stage 2.7 uses **uniform overlap blending**:

- Each window contributes weight `1.0` per pixel
- Overlapping predictions accumulate `prob_sum` and `weight_sum`
- Final probability: `prob_sum / weight_sum` where `weight_sum > 0`

This is deterministic and avoids hard seams at tile boundaries.

## Outputs

Written to the configured output directory:

```
predictions/
  prediction.tif       # int16, nodata=-1
  confidence.tif       # float32, nodata=0
  probabilities.tif    # 3-band float32
  inference.json
```

Optional per-class probability GeoTIFFs when
`save_individual_probability_bands=True`.

All rasters preserve input CRS, affine transform, width, height, and resolution
from the manifest. Outputs are not reprojected or resampled.

## CLI

```bash
poetry run python -m ssri_model.inference \
  --checkpoint ./experiments/exp-001/best.pt \
  --features ./feature_stack.npy \
  --manifest ./manifest.json \
  --statistics ./statistics.json \
  --output ./predictions \
  --tile-size 512 \
  --overlap 64 \
  --batch-size 4 \
  --device auto
```

## Device and Mixed Precision

- Device resolved via `resolve_device()` (`auto`, `cpu`, `cuda`)
- CPU inference is fully supported
- Mixed precision is **disabled by default**
- Enabling `--mixed-precision` on CPU raises `InvalidInferenceConfigError`
- CUDA mixed precision uses `torch.autocast` when explicitly enabled

## Determinism

Given the same checkpoint, feature stack, statistics, and configuration, repeated
runs produce identical outputs. Inference uses a fixed seed (`42`) and performs no
random augmentation.

## Limitations

- Requires a Stage 2.5 checkpoint with embedded `model_config`
- Requires compatible `statistics.json` covering all 13 canonical channels
- Does not perform on-the-fly feature engineering (Stage 1 stack must exist)
- Uniform overlap blending may leave minor edge effects near AOI boundaries
- `scientific_validation_status` is always `NOT_VALIDATED` — outputs are not
  claimed to be scientifically validated hazard assessments

## Scientific Validation Disclaimer

Inference artifacts are model predictions only. They must be independently reviewed
before operational geohazard use. This pipeline does not certify scientific validity.

## Readiness for Stage 2.8

Stage 2.7 provides production-oriented offline inference with windowed processing,
geospatial outputs, and full validation. Stage 2.8 can build on this foundation for
deployment packaging, batch orchestration, or service integration without changing
the core tensor or normalization contracts established here.
