"""Assert protocol spatial disjointness on frozen corpus (if present)."""
from __future__ import annotations

import json
import math
from pathlib import Path

POC = Path(__file__).resolve().parents[1]
CORPUS = POC / "corpus"
CONFIG = json.loads((POC / "config.json").read_text(encoding="utf-8"))


def haversine_km(lat1, lon1, lat2, lon2):
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def load_near():
    path = CORPUS / "samples_near.jsonl"
    if not path.exists():
        return []
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def test_blocks_disjoint_across_splits():
    rows = load_near()
    if not rows:
        return  # corpus not built yet
    by = {}
    for r in rows:
        by.setdefault(r["split"], set()).add(r["block"])
    assert not (by.get("train", set()) & by.get("test", set()))
    assert not (by.get("validation", set()) & by.get("test", set()))


def test_train_test_min_distance():
    rows = load_near()
    if not rows:
        return
    train = [r for r in rows if r["split"] == "train"]
    test = [r for r in rows if r["split"] == "test"]
    assert train and test
    buf = float(CONFIG["train_test_buffer_km"])
    for t in test:
        dmin = min(haversine_km(t["lat"], t["lon"], u["lat"], u["lon"]) for u in train)
        assert dmin >= buf - 1e-3, (t["sample_id"], dmin)
