"""Isolated DeepSlide landslide engine — NOT wired to /api/v1/assess.

Separate 14-band contract from SSRI Stage 2.5 (13-channel). Outputs are
uncalibrated segmentation scores, not calibrated risk probabilities.
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import torch
import torch.nn as nn

# Authoritative L4S packaging means (IARAI contributor YonghaoXu, issue #4)
IMG_MEAN = np.array(
    [
        1111.81236406,
        824.63171476,
        663.41636217,
        445.17289745,
        645.8582926,
        1547.73508126,
        1960.44401001,
        1941.32229668,
        674.07572865,
        9.04787384,
        1113.98338755,
        519.90397929,
        20.29228266,
        772.83144788,
    ],
    dtype=np.float64,
)

BAND_NAMES = tuple(
    [f"B{i:02d}" for i in range(1, 13)] + ["slope_deg", "dem_m"]
)
EXPECTED_CHANNELS = 14
DEFAULT_THRESHOLD = 0.5
PREPROCESS_VERSION = "l4s-pack-v1-div-img-mean"


@dataclass(frozen=True)
class DeepSlideContract:
    channels: int = EXPECTED_CHANNELS
    band_order: tuple[str, ...] = BAND_NAMES
    packaging: str = "raw_div_img_mean"
    preprocess_version: str = PREPROCESS_VERSION
    threshold: float = DEFAULT_THRESHOLD
    output_semantics: str = (
        "uncalibrated_sigmoid_segmentation_score_not_calibrated_probability_not_validated_risk"
    )
    hazards_supported: tuple[str, ...] = ("landslide",)
    not_supported: tuple[str, ...] = ("subsidence", "sinkhole")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def package_raw_stack(raw_chw: np.ndarray) -> np.ndarray:
    """Convert physical raw stack to L4S packaged domain.

    raw_chw: (14,H,W) float — optical scaled DN (~0-10000), slope degrees, DEM meters.
    """
    if raw_chw.ndim != 3 or raw_chw.shape[0] != EXPECTED_CHANNELS:
        raise ValueError(f"expected (14,H,W), got {raw_chw.shape}")
    arr = np.nan_to_num(raw_chw.astype(np.float64), nan=0.0, posinf=0.0, neginf=0.0)
    return (arr / IMG_MEAN[:, None, None]).astype(np.float32)


def build_model() -> nn.Module:
    import segmentation_models_pytorch as smp

    return smp.Unet(
        encoder_name="mobilenet_v2",
        encoder_weights=None,
        in_channels=EXPECTED_CHANNELS,
        classes=1,
    )


def load_checkpoint(model: nn.Module, path: Path) -> dict[str, Any]:
    state = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(state, dict):
        raise TypeError("checkpoint must be a state dict")
    cand = {k[len("model.model.") :]: v for k, v in state.items() if k.startswith("model.model.")}
    if not cand:
        raise ValueError("no model.model.* keys in checkpoint")
    missing, unexpected = model.load_state_dict(cand, strict=False)
    if missing:
        raise RuntimeError(f"missing keys: {missing[:5]}...")
    return {
        "loaded_keys": len(cand),
        "unexpected": len(unexpected),
        "sha256": sha256_file(path),
        "path": str(path),
    }


class DeepSlideEngine:
    """Landslide-only inference engine with explicit 14-band contract."""

    def __init__(self, checkpoint: Path, threshold: float = DEFAULT_THRESHOLD, device: str = "cpu"):
        if abs(threshold - DEFAULT_THRESHOLD) > 1e-12:
            # Allow explicit override but record it; production pin uses 0.5
            pass
        self.contract = DeepSlideContract(threshold=threshold)
        self.device = torch.device(device)
        self.checkpoint_path = Path(checkpoint)
        self.model = build_model()
        self.load_meta = load_checkpoint(self.model, self.checkpoint_path)
        self.model.eval().to(self.device)
        self.threshold = float(threshold)

    def predict_packaged(self, packaged_chw: np.ndarray) -> dict[str, Any]:
        if packaged_chw.ndim != 3 or packaged_chw.shape[0] != EXPECTED_CHANNELS:
            raise ValueError(f"packaged input must be (14,H,W), got {packaged_chw.shape}")
        if packaged_chw.dtype != np.float32:
            packaged_chw = packaged_chw.astype(np.float32)
        x = torch.from_numpy(np.nan_to_num(packaged_chw, nan=1e-6)).unsqueeze(0).to(self.device)
        with torch.no_grad():
            logits = self.model(x)
            score = torch.sigmoid(logits).squeeze().cpu().numpy().astype(np.float32)
        mask = (score > self.threshold).astype(np.uint8)
        return {
            "score": score,
            "mask": mask,
            "threshold": self.threshold,
            "semantics": self.contract.output_semantics,
            "preprocess_version": PREPROCESS_VERSION,
            "checkpoint_sha256": self.load_meta["sha256"],
            "pred_pos": int(mask.sum()),
            "score_max": float(score.max()),
            "score_min": float(score.min()),
        }

    def predict_raw(self, raw_chw: np.ndarray) -> dict[str, Any]:
        return self.predict_packaged(package_raw_stack(raw_chw))


def write_georef_prediction(
    out_path: Path,
    mask: np.ndarray,
    score: np.ndarray,
    *,
    crs: Any,
    transform: Any,
    tags: dict[str, str] | None = None,
) -> None:
    import rasterio

    profile = {
        "driver": "GTiff",
        "height": mask.shape[0],
        "width": mask.shape[1],
        "count": 2,
        "dtype": "float32",
        "crs": crs,
        "transform": transform,
        "compress": "lzw",
    }
    with rasterio.open(out_path, "w", **profile) as dst:
        dst.write(mask.astype(np.float32), 1)
        dst.write(score.astype(np.float32), 2)
        meta = {
            "BAND1": "binary_mask",
            "BAND2": "uncalibrated_sigmoid_score",
            "PREPROCESS": PREPROCESS_VERSION,
            "NOT_RISK": "true",
        }
        if tags:
            meta.update(tags)
        dst.update_tags(**meta)
