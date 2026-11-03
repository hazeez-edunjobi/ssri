import sys
from pathlib import Path

import numpy as np
import torch

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO / "model" / "src"))
from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.multitask import SSRIMultiTaskModel

ckpt = torch.load(REPO / "models" / "ssri-foundation-v2.pt", map_location="cpu", weights_only=False)
print("keys", list(ckpt.keys()))
state = ckpt["state_dict"]
model = SSRIMultiTaskModel(SSRIModelConfig(), dann=False)
missing, unexpected = model.load_state_dict(state, strict=False)
print("missing", len(missing))
print("\n".join(missing[:20]))
print("unexpected", len(unexpected))
print("\n".join(list(unexpected)[:20]))

sid = next((REPO / "data/datasets/usgs_landslide_featurestacks/v3/samples").iterdir())
arr = np.load(sid / "feature_stack.npy").astype(np.float32)
print("sid", sid.name, arr.shape)
NODATA = -9999.0
a = arr.copy()
for c in range(13):
    band = a[c]
    bad = (band == NODATA) | ~np.isfinite(band)
    band = band.copy()
    band[bad] = 0.0
    a[c] = band
th = tw = 64
c, h, w = a.shape
out = np.zeros((c, th, tw), np.float32)
dy, dx = min(h, th), min(w, tw)
out[:, :dy, :dx] = a[:, :dy, :dx]
x = torch.from_numpy(out[None])
model.eval()
with torch.no_grad():
    logits = model(x)
    for k, v in logits.items():
        s = torch.sigmoid(v)
        print(k, "logit", float(v.min()), float(v.max()), "sig_mean", float(s.mean()), "sig_minmax", float(s.min()), float(s.max()))
