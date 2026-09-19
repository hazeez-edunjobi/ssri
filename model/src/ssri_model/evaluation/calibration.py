"""Calibration / ROC reporting helpers.

These utilities generate reports from *real* prediction arrays only.
They never invent AUC or accuracy values. When labels/predictions are
unavailable, callers must mark metrics as PENDING REAL DATA.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np


def _validate_binary_arrays(
    y_true: np.ndarray,
    y_score: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    yt = np.asarray(y_true).astype(np.float64).ravel()
    ys = np.asarray(y_score).astype(np.float64).ravel()
    if yt.shape != ys.shape:
        raise ValueError("y_true and y_score must have the same shape")
    if yt.size == 0:
        raise ValueError("empty arrays")
    return yt, ys


def binary_confusion_at_threshold(
    y_true: np.ndarray,
    y_score: np.ndarray,
    *,
    threshold: float = 0.5,
) -> dict[str, float]:
    yt, ys = _validate_binary_arrays(y_true, y_score)
    pred = (ys >= threshold).astype(np.float64)
    tp = float(np.sum((pred == 1) & (yt == 1)))
    tn = float(np.sum((pred == 0) & (yt == 0)))
    fp = float(np.sum((pred == 1) & (yt == 0)))
    fn = float(np.sum((pred == 0) & (yt == 1)))
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (
        2 * precision * recall / (precision + recall)
        if (precision + recall)
        else 0.0
    )
    return {
        "threshold": float(threshold),
        "tp": tp,
        "tn": tn,
        "fp": fp,
        "fn": fn,
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "accuracy": (tp + tn) / float(yt.size),
    }


def roc_curve_points(
    y_true: np.ndarray,
    y_score: np.ndarray,
    *,
    num_thresholds: int = 101,
) -> list[dict[str, float]]:
    """Compute empirical ROC points without sklearn dependency."""
    yt, ys = _validate_binary_arrays(y_true, y_score)
    if np.unique(yt).size < 2:
        raise ValueError("ROC requires both positive and negative labels")
    # Include all unique scores plus endpoints for a faithful step curve.
    thresholds = np.unique(np.concatenate(([0.0, 1.0], ys, np.linspace(0.0, 1.0, num_thresholds))))
    thresholds = np.sort(thresholds)[::-1]
    points: list[dict[str, float]] = []
    positives = float(np.sum(yt == 1))
    negatives = float(np.sum(yt == 0))
    for thr in thresholds:
        pred = ys >= thr
        tpr = float(np.sum((pred) & (yt == 1))) / positives
        fpr = float(np.sum((pred) & (yt == 0))) / negatives
        points.append({"threshold": float(thr), "tpr": tpr, "fpr": fpr})
    return points


def mann_whitney_auc(y_true: np.ndarray, y_score: np.ndarray) -> float:
    """AUC via Mann–Whitney U (equivalent to ROC AUC for binary labels)."""
    yt, ys = _validate_binary_arrays(y_true, y_score)
    pos = ys[yt == 1]
    neg = ys[yt == 0]
    if pos.size == 0 or neg.size == 0:
        raise ValueError("AUC requires both positive and negative labels")
    # Rank comparison
    wins = 0.0
    for p in pos:
        wins += float(np.sum(p > neg)) + 0.5 * float(np.sum(p == neg))
    return wins / float(pos.size * neg.size)


def trapezoidal_auc(roc_points: list[dict[str, float]]) -> float:
    """AUC via trapezoidal rule on ROC points sorted by FPR."""
    ordered = sorted(roc_points, key=lambda p: p["fpr"])
    auc = 0.0
    for i in range(1, len(ordered)):
        x0, x1 = ordered[i - 1]["fpr"], ordered[i]["fpr"]
        y0, y1 = ordered[i - 1]["tpr"], ordered[i]["tpr"]
        auc += (x1 - x0) * (y0 + y1) / 2.0
    return float(auc)


def reliability_bins(
    y_true: np.ndarray,
    y_score: np.ndarray,
    *,
    n_bins: int = 10,
) -> list[dict[str, float]]:
    """Simple equal-width reliability diagram bins."""
    yt, ys = _validate_binary_arrays(y_true, y_score)
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bins: list[dict[str, float]] = []
    for i in range(n_bins):
        lo, hi = edges[i], edges[i + 1]
        mask = (ys >= lo) & (ys < hi if i < n_bins - 1 else ys <= hi)
        count = int(np.sum(mask))
        if count == 0:
            bins.append(
                {
                    "bin_low": float(lo),
                    "bin_high": float(hi),
                    "count": 0.0,
                    "mean_score": float("nan"),
                    "empirical_rate": float("nan"),
                }
            )
            continue
        bins.append(
            {
                "bin_low": float(lo),
                "bin_high": float(hi),
                "count": float(count),
                "mean_score": float(np.mean(ys[mask])),
                "empirical_rate": float(np.mean(yt[mask])),
            }
        )
    return bins


def build_calibration_report(
    *,
    y_true: np.ndarray | None,
    y_score: np.ndarray | None,
    dataset_name: str,
    dataset_version: str,
    model_version: str,
    notes: list[str] | None = None,
) -> dict[str, Any]:
    """Build a calibration/ROC report or a PENDING REAL DATA placeholder."""
    base: dict[str, Any] = {
        "dataset_name": dataset_name,
        "dataset_version": dataset_version,
        "model_version": model_version,
        "status": "PENDING_REAL_DATA",
        "metrics": None,
        "notes": list(notes or [])
        + [
            "Do not invent AUC/precision/recall. Populate only from real arrays.",
            "Software unit tests are not scientific validation.",
        ],
    }
    if y_true is None or y_score is None:
        return base
    try:
        roc = roc_curve_points(y_true, y_score)
        conf = binary_confusion_at_threshold(y_true, y_score)
        base["status"] = "COMPUTED_FROM_PROVIDED_ARRAYS"
        base["metrics"] = {
            "auc": mann_whitney_auc(y_true, y_score),
            "auc_trapezoidal_roc": trapezoidal_auc(roc),
            "confusion_at_0_5": conf,
            "roc_points": roc,
            "reliability_bins": reliability_bins(y_true, y_score),
        }
    except ValueError as exc:
        base["status"] = "PENDING_REAL_DATA"
        base["notes"].append(f"metrics_unavailable: {exc}")
    return base


def save_calibration_report(path: Path | str, report: dict[str, Any]) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return destination
