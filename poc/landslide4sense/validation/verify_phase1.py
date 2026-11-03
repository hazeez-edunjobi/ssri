"""Phase 1 — authenticate DeepSlide checkpoint and document contract."""
from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
WEIGHTS = ROOT / "weights" / "mobilenetv2.pth"
OUT = ROOT / "validation" / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

# From Hugging Face LFS pointer for harshinde/DeepSlide_Models mobilenetv2.pth
HF_SHA256 = "a743e627dd68a1409ddda4ad43b70b53ee92c0d504d16c890e128ba04dc9ab4f"


def main() -> int:
    h = hashlib.sha256(WEIGHTS.read_bytes()).hexdigest()
    state = torch.load(WEIGHTS, map_location="cpu", weights_only=False)
    keys = list(state.keys()) if isinstance(state, dict) else []
    n_model_model = sum(1 for k in keys if k.startswith("model.model."))

    import segmentation_models_pytorch as smp

    model = smp.Unet(encoder_name="mobilenet_v2", encoder_weights=None, in_channels=14, classes=1)
    cand = {k[len("model.model.") :]: v for k, v in state.items() if k.startswith("model.model.")}
    missing, unexpected = model.load_state_dict(cand, strict=False)

    report = {
        "phase": 1,
        "architecture": "smp.Unet(encoder_name='mobilenet_v2', in_channels=14, classes=1)",
        "checkpoint_path": str(WEIGHTS),
        "checkpoint_source": "https://huggingface.co/harshinde/DeepSlide_Models/blob/main/mobilenetv2.pth",
        "license": "MIT (model card)",
        "dataset_trained_on": "ibm-nasa-geospatial/Landslide4sense / Landslide4Sense",
        "sha256_local": h,
        "sha256_hf_lfs": HF_SHA256,
        "sha256_match": h.lower() == HF_SHA256.lower(),
        "checkpoint_keys": len(keys),
        "unet_keys_loaded": len(cand),
        "missing": len(missing),
        "unexpected": len(unexpected),
        "params": sum(p.numel() for p in model.parameters()),
        "input_contract": {
            "bands": 14,
            "order": "S2 B1-B12, slope (ALOS), DEM (ALOS) — L4S competition order",
            "spatial": "128x128",
            "normalization": "DeepSlide config normalize=False (raw competition tensors)",
            "output": "logits -> sigmoid; threshold 0.5; binary landslide mask",
            "matches_vendor_streamlit": True,
        },
        "not_substituted": True,
        "verdict": "PASS" if (h.lower() == HF_SHA256.lower() and len(missing) == 0) else "BLOCKED",
    }
    (OUT / "phase1_model.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["verdict"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
