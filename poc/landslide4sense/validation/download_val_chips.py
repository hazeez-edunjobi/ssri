"""Download Landslide4Sense validation chips + masks from HF for held-out eval."""
from __future__ import annotations

import sys
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT_IMG = ROOT / "data" / "validation" / "images"
OUT_MSK = ROOT / "data" / "validation" / "masks"
OUT_IMG.mkdir(parents=True, exist_ok=True)
OUT_MSK.mkdir(parents=True, exist_ok=True)

# Prefer ibm-nasa mirror structure; fall back to harshinde
BASES = [
    (
        "https://huggingface.co/datasets/ibm-nasa-geospatial/Landslide4sense/resolve/main/images/validation/image_{i}.h5",
        "https://huggingface.co/datasets/ibm-nasa-geospatial/Landslide4sense/resolve/main/annotations/validation/mask_{i}.h5",
    ),
    (
        "https://huggingface.co/datasets/harshinde/LandSlide4Sense/resolve/main/images/validation/image_{i}.h5",
        "https://huggingface.co/datasets/harshinde/LandSlide4Sense/resolve/main/annotations/validation/mask_{i}.h5",
    ),
]

# 40 chips: enough for micro metrics, bounded download (~40 * ~1.8MB ≈ 72MB + masks)
IDS = list(range(1, 41))


def fetch(url: str, dest: Path) -> bool:
    if dest.exists() and dest.stat().st_size > 1000:
        print(f"skip {dest.name}", flush=True)
        return True
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "ssri-poc-validation/1.0"})
        with urllib.request.urlopen(req, timeout=120) as resp:
            data = resp.read()
        if len(data) < 1000:
            print(f"too small {url} -> {len(data)}", flush=True)
            return False
        dest.write_bytes(data)
        print(f"ok {dest.name} {len(data)}", flush=True)
        return True
    except Exception as exc:  # noqa: BLE001
        print(f"fail {url}: {exc}", flush=True)
        return False


def main() -> int:
    ok = 0
    for i in IDS:
        img_ok = msk_ok = False
        for img_t, msk_t in BASES:
            img_url = img_t.format(i=i)
            msk_url = msk_t.format(i=i)
            img_dest = OUT_IMG / f"image_{i}.h5"
            msk_dest = OUT_MSK / f"mask_{i}.h5"
            if fetch(img_url, img_dest):
                img_ok = True
            if fetch(msk_url, msk_dest):
                msk_ok = True
            if img_ok and msk_ok:
                break
        if img_ok and msk_ok:
            ok += 1
        else:
            print(f"incomplete chip {i}", flush=True)
    print(f"complete_pairs={ok}/{len(IDS)}", flush=True)
    return 0 if ok >= 30 else 2


if __name__ == "__main__":
    raise SystemExit(main())
