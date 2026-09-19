# Stage 2.3 — SSRI Model Architecture

## Purpose

Stage 2.3 defines the baseline **SSRI U-Net segmentation model** that maps
13-channel geospatial feature tensors to dense, per-pixel geohazard logits.

This model is **not trained yet**. Stage 2.4 will add the training loop,
loss functions, and checkpointing.

## Input Contract

| Property | Value |
|----------|-------|
| Tensor | `features` |
| Shape | `(B, 13, H, W)` |
| Dtype | `float32` |
| Channels | Stage 1 / Stage 2.0 canonical order |

The 13 channels are:

1. elevation
2. slope
3. plan_curvature
4. profile_curvature
5. twi
6. relative_relief
7. valley_depth
8. ndvi
9. ndwi
10. clay_mineral_ratio
11. iron_oxide_index
12. gravity
13. magnetics

Invalid inputs (wrong rank, wrong channel count) raise `InvalidInputTensorError`.

## Output Contract

| Property | Value |
|----------|-------|
| Tensor | logits |
| Shape | `(B, 3, H, W)` |
| Dtype | `float32` |
| Activation | none (raw logits) |

Class channel mapping:

| Channel | Hazard |
|---------|--------|
| 0 | subsidence |
| 1 | landslide |
| 2 | sinkhole |

Softmax / sigmoid conversion belongs to the training and inference stages,
not the model itself.

## Architecture Diagram

```text
Input (B, 13, H, W)
        │
        ▼
   Stem ConvBlock → 32 channels
        │
        ├─ skip₀ (H, W)
        ▼
   Encoder Stage 1 → 64 channels + downsample
        │
        ├─ skip₁ (H/2, W/2)
        ▼
   Encoder Stage 2 → 128 channels + downsample
        │
        ├─ skip₂ (H/4, W/4)
        ▼
   Encoder Stage 3 + downsample
        ▼
   Bottleneck → 256 channels (H/8, W/8)
        ▼
   Decoder Stage 1 ← skip₂
        ▼
   Decoder Stage 2 ← skip₁
        ▼
   Decoder Stage 3 ← skip₀
        ▼
   1×1 Segmentation Head
        ▼
Output (B, 3, H, W)
```

## Components

| Module | Role |
|--------|------|
| `blocks.py` | ConvBlock, Downsample, Upsample, spatial alignment |
| `encoder.py` | Progressive downsampling with skip features |
| `decoder.py` | Upsampling + skip concatenation |
| `heads.py` | 1×1 segmentation head |
| `model.py` | `SSRIModel`, factory, parameter utilities |
| `config.py` | `SSRIModelConfig` |

## Configuration

`SSRIModelConfig` defaults:

```python
SSRIModelConfig(
    in_channels=13,
    num_classes=3,
    base_channels=32,
    num_encoder_stages=3,
    dropout=0.0,
    normalization="group",
    activation="relu",
)
```

Encoder channel widths: `32 → 64 → 128`, bottleneck `256`.

Normalization options: `group` (default), `batch`, `identity`.

## Parameter Count

Use:

```python
from ssri_model.architecture import count_parameters, format_parameter_summary

summary = count_parameters(model)
print(format_parameter_summary(model))
```

## Spatial Dimensions

The model supports arbitrary `H × W` sizes. Because the encoder applies three
2× downsampling stages, the decoder uses bilinear upsampling plus explicit
`align_spatial()` calls to restore **exact** input height and width — including
odd sizes such as `101 × 137`.

## Nodata / Mask Handling

Stage 2.2 provides a boolean `mask` tensor for valid pixels. **The model does
not accept or infer nodata.** Masking is applied during training and evaluation
in later stages.

## Limitations

- Baseline U-Net only; no transformer or attention blocks
- No auxiliary heads yet
- No mixed precision
- No built-in probability calibration

## Future Extension Points

- Auxiliary uncertainty head
- Deep supervision at decoder stages
- Attention gates on skip connections
- TorchScript / ONNX export hooks

## Public API

```python
from ssri_model.architecture import SSRIModel, SSRIModelConfig, create_ssri_model

model = create_ssri_model()
logits = model(features)
```
