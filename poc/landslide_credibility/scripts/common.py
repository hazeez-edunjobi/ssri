"""Shared helpers for landslide credibility cycle."""
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
OUT = POC / "outputs"
CORPUS = POC / "corpus"
OUT.mkdir(parents=True, exist_ok=True)
CORPUS.mkdir(parents=True, exist_ok=True)

CATALOG = REPO / "data" / "catalogs" / "usgs_landslide_v3" / "catalog.jsonl"
PROTOCOL_V1 = REPO / "poc" / "landslide_due_diligence" / "PROTOCOL.md"
PROTOCOL_V2 = POC / "PROTOCOL_v2.md"
CONFIG = json.loads((POC / "config.json").read_text(encoding="utf-8"))

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
    d = float(CONFIG["block_deg"])
    return f"{int(math.floor(lat / d) * d)}_{int(math.floor(lon / d) * d)}"


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


def roc_auc(y: np.ndarray, s: np.ndarray) -> float | None:
    y = y.astype(np.int32)
    if y.min() == y.max():
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


def brier(y: np.ndarray, s: np.ndarray) -> float:
    return float(np.mean((s - y.astype(np.float64)) ** 2))


def ece(y: np.ndarray, s: np.ndarray, n_bins: int = 10) -> float:
    y = y.astype(np.float64)
    s = np.clip(s.astype(np.float64), 0, 1)
    bins = np.linspace(0.0, 1.0, n_bins + 1)
    total = 0.0
    n = len(y)
    for i in range(n_bins):
        m = (s >= bins[i]) & (s < bins[i + 1] if i < n_bins - 1 else s <= bins[i + 1])
        if not np.any(m):
            continue
        total += (m.sum() / n) * abs(y[m].mean() - s[m].mean())
    return float(total)


def bootstrap_block(
    y: np.ndarray,
    s: np.ndarray,
    blocks: list[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    uniq = sorted(set(blocks))
    by_b = {b: [i for i, bb in enumerate(blocks) if bb == b] for b in uniq}

    def pack(idxs: list[int]) -> dict:
        yy, ss = y[idxs], s[idxs]
        return {
            "roc_auc": roc_auc(yy, ss),
            "pr_auc": pr_auc(yy, ss),
            "brier": brier(yy, ss),
            "ece": ece(yy, ss),
        }

    point = pack(list(range(len(y))))
    samples = {k: [] for k in point}
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idxs: list[int] = []
        for b in chosen:
            idxs.extend(by_b[b])
        m = pack(idxs)
        for k, v in m.items():
            if v is not None:
                samples[k].append(v)
    out = {"point": point, "ci95": {}, "n_blocks": len(uniq), "n": len(y)}
    for k, arr in samples.items():
        a = np.asarray(arr, dtype=np.float64)
        out["ci95"][k] = (
            [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
            if len(a) >= 10
            else None
        )
    return out


def delta_auc_boot(
    y: np.ndarray,
    s_cand: np.ndarray,
    s_base: np.ndarray,
    blocks: list[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict:
    rng = np.random.default_rng(seed)
    uniq = sorted(set(blocks))
    by_b = {b: [i for i, bb in enumerate(blocks) if bb == b] for b in uniq}
    pc, pb = roc_auc(y, s_cand), roc_auc(y, s_base)
    point = None if pc is None or pb is None else pc - pb
    deltas = []
    for _ in range(n_boot):
        chosen = rng.choice(uniq, size=len(uniq), replace=True)
        idxs: list[int] = []
        for b in chosen:
            idxs.extend(by_b[b])
        c, b = roc_auc(y[idxs], s_cand[idxs]), roc_auc(y[idxs], s_base[idxs])
        if c is not None and b is not None:
            deltas.append(c - b)
    a = np.asarray(deltas, dtype=np.float64)
    return {
        "delta_point": point,
        "candidate_auc": pc,
        "slope_auc": pb,
        "ci95": [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))]
        if len(a) >= 10
        else None,
        "n_boot_ok": int(len(a)),
    }
