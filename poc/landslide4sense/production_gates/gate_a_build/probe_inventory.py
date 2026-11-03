"""Probe USGS catalog + feature-stack absence pools (run from repo root)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

REPO = Path(__file__).resolve().parents[4]
CATALOG = REPO / "data" / "catalogs" / "usgs_landslide_v3" / "catalog.jsonl"
FS_SAMPLES = REPO / "data" / "datasets" / "usgs_landslide_featurestacks" / "v3" / "samples"


def main() -> None:
    n = 0
    years: Counter[str] = Counter()
    blocks: Counter[str] = Counter()
    samples = []
    with CATALOG.open(encoding="utf-8") as f:
        for line in f:
            n += 1
            o = json.loads(line)
            lat, lon = o.get("latitude"), o.get("longitude")
            if lat is None or lon is None:
                continue
            if lat < 24 or lat > 49 or lon < -125 or lon > -66:
                continue
            q = "|".join(o.get("quality_flags") or [])
            if "confidence=1" in q or "confidence=2" in q:
                continue
            ts = (o.get("timestamp") or "")[:4]
            if ts.isdigit() and int(ts) < 2017:
                continue
            block = f"{int(lat // 5) * 5}_{int(lon // 5) * 5}"
            samples.append(o)
            years[ts] += 1
            blocks[block] += 1

    print("catalog total", n, "filtered CONUS", len(samples), "blocks", len(blocks))
    print("top blocks", blocks.most_common(10))
    print("years", years.most_common(12))

    pa = pr = 0
    for d in FS_SAMPLES.iterdir():
        if not d.is_dir():
            continue
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        lab = meta.get("labels", {}).get("landslide")
        if str(d.name).startswith("pseudo") or lab == 0:
            pa += 1
        elif lab == 1:
            pr += 1
    print("featurestack presence", pr, "pseudo", pa)


if __name__ == "__main__":
    main()
