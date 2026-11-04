import numpy as np
from pathlib import Path

from ssri_model.ml.constants import CHANNEL_NAMES, FEATURE_NODATA

root = Path(__file__).resolve().parents[3] / "data/datasets/usgs_landslide_featurestacks/v3/samples"
dirs = sorted(p for p in root.iterdir() if p.is_dir())
print("n", len(dirs))
sums = {n: [] for n in CHANNEL_NAMES}
for d in dirs:
    a = np.load(d / "feature_stack.npy")
    for i, n in enumerate(CHANNEL_NAMES):
        m = (~np.isfinite(a[i])) | (a[i] == FEATURE_NODATA)
        sums[n].append(float(m.mean()))
for n in CHANNEL_NAMES:
    print(n, "mean_nd", float(np.mean(sums[n])), "min", min(sums[n]), "max", max(sums[n]))
