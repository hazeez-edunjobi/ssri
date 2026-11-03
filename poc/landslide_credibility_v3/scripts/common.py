"""Shared helpers for credibility v3."""
from __future__ import annotations

import hashlib
import json
import math
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[3]
POC = Path(__file__).resolve().parents[1]
V2 = REPO / "poc" / "landslide_credibility"
OUT = POC / "outputs"
CORPUS = POC / "corpus"
OUT.mkdir(parents=True, exist_ok=True)
CORPUS.mkdir(parents=True, exist_ok=True)

PROTOCOL_V1 = REPO / "poc" / "landslide_due_diligence" / "PROTOCOL.md"
PROTOCOL_V2 = V2 / "PROTOCOL_v2.md"
PROTOCOL_V3 = POC / "PROTOCOL_v3.md"
CATALOG = REPO / "data" / "catalogs" / "usgs_landslide_v3" / "catalog.jsonl"

FEATURE_NAMES = (
    "elevation",
    "slope",
    "aspect_sin",
    "aspect_cos",
    "plan_curvature",
    "profile_curvature",
    "twi",
    "relative_relief_1km",
    "valley_depth",
    "tpi",
)

SPENT_V2_TEST = {"35_-125", "40_-120", "40_-125", "45_-120", "45_-75"}
SEALED_FRESH = ["40_-115", "30_-105", "35_-105", "45_-115", "55_-150", "20_-155", "15_-65"]
SEEDS = [42, 43, 44, 45, 46]


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def append_log(msg: str) -> None:
    with (OUT / "run_log.txt").open("a", encoding="utf-8") as f:
        f.write(f"{datetime.now(timezone.utc).isoformat()} {msg}\n")


def block5(lat: float, lon: float) -> str:
    return f"{int(math.floor(lat / 5.0) * 5)}_{int(math.floor(lon / 5.0) * 5)}"


def haversine_km(lat1, lon1, lat2, lon2) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def roc_auc(y: np.ndarray, s: np.ndarray) -> float | None:
    y = y.astype(np.int32)
    if len(y) < 2 or y.min() == y.max():
        return None
    order = np.argsort(s)
    ranks = np.empty(len(s), dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1, dtype=np.float64)
    n_pos = float(y.sum())
    n_neg = float(len(y) - n_pos)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def pr_auc(y: np.ndarray, s: np.ndarray) -> float | None:
    y = y.astype(np.int32)
    if y.sum() == 0:
        return None
    order = np.argsort(-s)
    y_s = y[order]
    tp = np.cumsum(y_s)
    fp = np.cumsum(1 - y_s)
    recall = tp / y_s.sum()
    precision = tp / np.maximum(tp + fp, 1e-12)
    recall = np.concatenate([[0.0], recall])
    precision = np.concatenate([[1.0], precision])
    trapz = getattr(np, "trapezoid", None) or np.trapz
    return float(trapz(precision, recall))


def brier(y, s) -> float:
    return float(np.mean((s - y.astype(np.float64)) ** 2))


def ece(y, s, n_bins: int = 10) -> float:
    y = y.astype(np.float64)
    s = np.clip(s.astype(np.float64), 0, 1)
    bins = np.linspace(0, 1, n_bins + 1)
    total = 0.0
    n = len(y)
    for i in range(n_bins):
        m = (s >= bins[i]) & (s < bins[i + 1] if i < n_bins - 1 else s <= bins[i + 1])
        if np.any(m):
            total += (m.sum() / n) * abs(y[m].mean() - s[m].mean())
    return float(total)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows
