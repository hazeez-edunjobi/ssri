"""Shared helpers for landslide due-diligence (poc only)."""
from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np

REPO = Path(__file__).resolve().parents[3]
POC = Path(__file__).resolve().parents[1]
OUT = POC / "outputs"
OUT.mkdir(parents=True, exist_ok=True)

FEATURESTACKS = REPO / "data" / "datasets" / "usgs_landslide_featurestacks" / "v3"
CATALOG = REPO / "data" / "catalogs" / "usgs_landslide_v3" / "catalog.jsonl"
CATALOG_MANIFEST = REPO / "data" / "catalogs" / "usgs_landslide_v3" / "manifest.json"
FOUNDATION_V2 = REPO / "models" / "ssri-foundation-v2.pt"
PROTOCOL = POC / "PROTOCOL.md"

CHANNEL_NAMES = (
    "elevation",
    "slope",
    "plan_curvature",
    "profile_curvature",
    "twi",
    "relative_relief",
    "valley_depth",
    "ndvi",
    "ndwi",
    "clay_mineral_ratio",
    "iron_oxide_index",
    "gravity",
    "magnetics",
)
TERRAIN_IDX = list(range(0, 7))
SPECTRAL_IDX = [7, 8, 9, 10]
NODATA = -9999.0


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest().upper()


def block5(lat: float, lon: float) -> str:
    return f"{int(math.floor(lat / 5.0) * 5)}_{int(math.floor(lon / 5.0) * 5)}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, default=str), encoding="utf-8")


def append_run_log(line: str) -> None:
    log = OUT / "run_log.txt"
    with log.open("a", encoding="utf-8") as f:
        f.write(line.rstrip() + "\n")


def roc_auc(y: np.ndarray, s: np.ndarray) -> float | None:
    y = y.astype(np.int32)
    if y.min() == y.max():
        return None
    order = np.argsort(s)
    y_sorted = y[order]
    ranks = np.empty_like(s, dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1, dtype=np.float64)
    n_pos = float(y.sum())
    n_neg = float(len(y) - n_pos)
    sum_ranks_pos = ranks[y == 1].sum()
    return float((sum_ranks_pos - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


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
    # append start
    recall = np.concatenate([[0.0], recall])
    precision = np.concatenate([[1.0], precision])
    trapz = getattr(np, "trapezoid", None) or getattr(np, "trapz")
    return float(trapz(precision, recall))


def brier(y: np.ndarray, s: np.ndarray) -> float:
    return float(np.mean((s - y.astype(np.float64)) ** 2))


def ece(y: np.ndarray, s: np.ndarray, n_bins: int = 10) -> float:
    y = y.astype(np.float64)
    s = s.astype(np.float64)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    n = len(y)
    for i in range(n_bins):
        m = (s >= bins[i]) & (s < bins[i + 1] if i < n_bins - 1 else s <= bins[i + 1])
        if not np.any(m):
            continue
        total += (m.sum() / n) * abs(y[m].mean() - s[m].mean())
    return float(total)


def bootstrap_block_metrics(
    y: np.ndarray,
    s: np.ndarray,
    blocks: list[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    """Resample unique blocks with replacement; recompute tile metrics."""
    rng = np.random.default_rng(seed)
    uniq = sorted(set(blocks))
    by_b: dict[str, list[int]] = {b: [] for b in uniq}
    for i, b in enumerate(blocks):
        by_b[b].append(i)

    def pack(idxs: list[int]) -> dict[str, float | None]:
        yy = y[idxs]
        ss = s[idxs]
        return {
            "roc_auc": roc_auc(yy, ss),
            "pr_auc": pr_auc(yy, ss),
            "brier": brier(yy, ss),
            "ece": ece(yy, ss),
        }

    point = pack(list(range(len(y))))
    keys = ["roc_auc", "pr_auc", "brier", "ece"]
    samples = {k: [] for k in keys}
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idxs: list[int] = []
        for b in chosen:
            idxs.extend(by_b[b])
        m = pack(idxs)
        for k in keys:
            if m[k] is not None:
                samples[k].append(m[k])

    ci = {}
    for k in keys:
        arr = np.asarray(samples[k], dtype=np.float64)
        if len(arr) < 10:
            ci[k] = {"point": point[k], "ci95": None, "n_boot_ok": int(len(arr))}
        else:
            ci[k] = {
                "point": point[k],
                "ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))],
                "n_boot_ok": int(len(arr)),
            }
    return {"point": point, "bootstrap": ci, "n_blocks": len(uniq), "n_tiles": len(y)}


def delta_auc_bootstrap(
    y: np.ndarray,
    s_cand: np.ndarray,
    s_base: np.ndarray,
    blocks: list[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    uniq = sorted(set(blocks))
    by_b: dict[str, list[int]] = {b: [] for b in uniq}
    for i, b in enumerate(blocks):
        by_b[b].append(i)
    point_c = roc_auc(y, s_cand)
    point_b = roc_auc(y, s_base)
    point_d = None if point_c is None or point_b is None else point_c - point_b
    deltas = []
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idxs: list[int] = []
        for b in chosen:
            idxs.extend(by_b[b])
        c = roc_auc(y[idxs], s_cand[idxs])
        b = roc_auc(y[idxs], s_base[idxs])
        if c is not None and b is not None:
            deltas.append(c - b)
    arr = np.asarray(deltas, dtype=np.float64)
    return {
        "delta_roc_auc_point": point_d,
        "candidate_roc_auc": point_c,
        "slope_roc_auc": point_b,
        "ci95": [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]
        if len(arr) >= 10
        else None,
        "n_boot_ok": int(len(arr)),
    }
