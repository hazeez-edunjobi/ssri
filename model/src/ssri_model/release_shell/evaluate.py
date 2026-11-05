"""Held-out block evaluation with majority / slope baselines and gates."""

from __future__ import annotations

import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np
import torch

from ssri_model.inference.checkpoint import load_inference_checkpoint
from ssri_model.ml.constants import CHANNEL_NAMES, LABEL_NODATA
from ssri_model.ml.labels import label_class_names
from ssri_model.release_shell.flags import default_limitations
from ssri_model.release_shell.gates import gate_hazard_status
from ssri_model.release_shell.probability import logits_to_class_probabilities


def _roc_auc(y: np.ndarray, s: np.ndarray) -> float | None:
    y = y.astype(np.int32)
    if len(y) < 2 or y.min() == y.max():
        return None
    order = np.argsort(s)
    ranks = np.empty(len(s), dtype=np.float64)
    ranks[order] = np.arange(1, len(s) + 1, dtype=np.float64)
    n_pos = float(y.sum())
    n_neg = float(len(y) - n_pos)
    return float((ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2.0) / (n_pos * n_neg))


def _pr_auc(y: np.ndarray, s: np.ndarray) -> float | None:
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


def _pick_thr(y: np.ndarray, s: np.ndarray) -> float:
    best_t, best_j = 0.5, -1.0
    for t in np.linspace(0.05, 0.95, 19):
        pred = (s >= t).astype(int)
        tp = ((pred == 1) & (y == 1)).sum()
        tn = ((pred == 0) & (y == 0)).sum()
        fp = ((pred == 1) & (y == 0)).sum()
        fn = ((pred == 0) & (y == 1)).sum()
        tpr = tp / max(tp + fn, 1)
        fpr = fp / max(fp + tn, 1)
        j = tpr - fpr
        if j > best_j:
            best_j, best_t = float(j), float(t)
    return best_t


def _metrics_at(y: np.ndarray, s: np.ndarray, thr: float) -> dict[str, Any]:
    pred = (s >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-12)
    iou = tp / max(tp + fp + fn, 1)
    return {
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "iou": iou,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
    }


def _bootstrap_delta(
    y: np.ndarray,
    s_model: np.ndarray,
    s_slope: np.ndarray,
    blocks: list[str],
    n_boot: int = 1000,
    seed: int = 42,
) -> dict[str, Any]:
    rng = np.random.default_rng(seed)
    uniq = sorted(set(blocks))
    by = {b: [i for i, bb in enumerate(blocks) if bb == b] for b in uniq}
    am = _roc_auc(y, s_model)
    as_ = _roc_auc(y, s_slope)
    point = None if am is None or as_ is None else am - as_
    deltas, aucs = [], []
    for _ in range(n_boot):
        ch = rng.choice(uniq, size=len(uniq), replace=True) if uniq else []
        idxs: list[int] = []
        for b in ch:
            idxs.extend(by[b])
        if len(idxs) < 2:
            continue
        idxs_a = np.asarray(idxs)
        c = _roc_auc(y[idxs_a], s_model[idxs_a])
        b = _roc_auc(y[idxs_a], s_slope[idxs_a])
        if c is not None:
            aucs.append(c)
        if c is not None and b is not None:
            deltas.append(c - b)

    def ci(a: list[float]) -> list[float] | None:
        if len(a) < 10:
            return None
        arr = np.asarray(a, float)
        return [float(np.percentile(arr, 2.5)), float(np.percentile(arr, 97.5))]

    return {
        "auc_point": am,
        "slope_auc_point": as_,
        "delta_point": point,
        "auc_ci95": ci(aucs),
        "delta_ci95": ci(deltas),
    }


def _load_tile(sample_dir: Path) -> tuple[np.ndarray, np.ndarray, dict[str, Any]]:
    feats = np.load(sample_dir / "feature_stack.npy").astype(np.float32)
    import rasterio

    with rasterio.open(sample_dir / "label.tif") as ds:
        lab = ds.read(1)
    meta = {}
    mp = sample_dir / "metadata.json"
    if mp.exists():
        meta = json.loads(mp.read_text(encoding="utf-8"))
    return feats, lab, meta


def evaluate_checkpoint_on_held_out(
    *,
    dataset_root: Path | str,
    checkpoint_path: Path | str,
    split_manifest: dict[str, Any] | None = None,
    seeds_note: list[int] | None = None,
) -> dict[str, Any]:
    """Evaluate on test (held-out) tiles only; threshold chosen on validation."""
    root = Path(dataset_root)
    ckpt = Path(checkpoint_path)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    splits = (split_manifest or {}).get("splits") or manifest.get("splits") or {}
    test_ids = list(splits.get("test") or [])
    val_ids = list(splits.get("validation") or [])
    if not test_ids:
        return {
            "status": "FAIL",
            "message": "No held-out test tiles in split manifest.",
            "limitations": default_limitations(),
        }

    model, payload = load_inference_checkpoint(str(ckpt), device=torch.device("cpu"))
    model.eval()
    slope_i = CHANNEL_NAMES.index("slope")
    hazards = list(label_class_names())

    def locate(sid: str) -> Path | None:
        for split in ("train", "validation", "test"):
            p = root / split / sid
            if p.is_dir():
                return p
        return None

    def collect(ids: list[str]) -> list[dict[str, Any]]:
        rows = []
        for sid in ids:
            p = locate(sid)
            if p is None:
                continue
            feats, lab, meta = _load_tile(p)
            with torch.no_grad():
                logits = model(torch.from_numpy(feats).unsqueeze(0))
                probs = logits_to_class_probabilities(logits)[0].cpu().numpy()
            block = meta.get("block") or "unknown"
            lat = meta.get("centroid_lat", meta.get("lat"))
            lon = meta.get("centroid_lon", meta.get("lon"))
            if lat is not None and lon is not None:
                from ssri_model.release_shell.spatial_split import block5

                block = block5(float(lat), float(lon))
            rows.append(
                {
                    "id": sid,
                    "block": block,
                    "probs": probs,
                    "label": lab,
                    "slope": feats[slope_i],
                }
            )
        return rows

    val_rows = collect(val_ids)
    test_rows = collect(test_ids)
    if not test_rows:
        return {
            "status": "FAIL",
            "message": "Held-out tiles could not be loaded.",
            "limitations": default_limitations(),
        }

    data_hash = hashlib.sha256(
        (root / "manifest.json").read_bytes()
    ).hexdigest().upper()
    ckpt_hash = hashlib.sha256(ckpt.read_bytes()).hexdigest().upper()

    per_hazard: dict[str, Any] = {}
    for hi, hname in enumerate(hazards):
        # pixel samples (subsample for speed)
        def pix(rows: list[dict[str, Any]]) -> tuple[np.ndarray, np.ndarray, np.ndarray, list[str]]:
            ys, sm, ss, bs = [], [], [], []
            for r in rows:
                lab = r["label"]
                valid = lab != LABEL_NODATA
                # binary: class hi vs other valid
                y = (lab == hi).astype(np.int32)
                score = r["probs"][hi]
                slope = r["slope"]
                # flatten subsample
                idx = np.where(valid)
                if idx[0].size == 0:
                    continue
                step = max(1, idx[0].size // 200)
                for k in range(0, idx[0].size, step):
                    i, j = int(idx[0][k]), int(idx[1][k])
                    ys.append(int(y[i, j]))
                    sm.append(float(score[i, j]))
                    ss.append(float(slope[i, j]))
                    bs.append(r["block"])
            return (
                np.asarray(ys, int),
                np.asarray(sm, float),
                np.asarray(ss, float),
                bs,
            )

        yv, svm, svs, _ = pix(val_rows)
        yt, stm, sts, blocks = pix(test_rows)
        if len(yt) < 10 or len(set(yt.tolist())) < 2:
            per_hazard[hname] = {
                "status": "insufficient_pixels",
                "gate_status": "trained, no demonstrated skill beyond slope",
                "message": "Not enough labelled pixels on held-out blocks.",
            }
            continue

        # slope-only: CDF vs train/val slopes of positives? use val slopes ranking
        ref = np.sort(svs) if len(svs) else np.sort(sts)
        slope_score_t = np.searchsorted(ref, sts, side="right") / max(len(ref), 1)
        maj = float(yv.mean()) if len(yv) else 0.5
        maj_score = np.full_like(stm, maj, dtype=float)

        thr = _pick_thr(yv, svm) if len(yv) and len(set(yv.tolist())) > 1 else 0.5
        thr_slope = _pick_thr(yv, np.searchsorted(ref, svs, side="right") / max(len(ref), 1)) if len(yv) else 0.5

        boot = _bootstrap_delta(yt, stm, slope_score_t, blocks)
        at = _metrics_at(yt, stm, thr)
        near_const = bool(float(np.std(stm)) < 1e-6)

        # per-block AUC
        per_block = {}
        for b in sorted(set(blocks)):
            idxs = [i for i, bb in enumerate(blocks) if bb == b]
            yy = yt[idxs]
            if len(set(yy.tolist())) < 2:
                per_block[b] = {"n": len(idxs), "roc_auc": None}
            else:
                per_block[b] = {
                    "n": len(idxs),
                    "n_pos": int(yy.sum()),
                    "roc_auc": _roc_auc(yy, stm[idxs]),
                }
        both = [v for v in per_block.values() if v.get("n_pos", 0) > 0 and v["n"] - v.get("n_pos", 0) > 0]
        frac = (
            sum(1 for v in both if v["roc_auc"] is not None and v["roc_auc"] > 0.5)
            / max(len(both), 1)
        )
        gate = gate_hazard_status(
            delta_ci95=boot.get("delta_ci95"),
            frac_blocks_auc_gt_0_5=frac,
        )
        brier = float(np.mean((stm - yt.astype(float)) ** 2))
        # ECE informational
        bins = np.linspace(0, 1, 11)
        ece = 0.0
        for i in range(10):
            m = (stm >= bins[i]) & (stm < bins[i + 1] if i < 9 else stm <= bins[i + 1])
            if np.any(m):
                ece += (m.sum() / len(stm)) * abs(yt[m].mean() - stm[m].mean())

        per_hazard[hname] = {
            "gate_status": gate,
            "roc_auc": boot["auc_point"],
            "pr_auc": _pr_auc(yt, stm),
            "threshold_from_validation": thr,
            **at,
            "baselines": {
                "majority_constant_score": maj,
                "slope_only_auc": boot["slope_auc_point"],
                "slope_threshold": thr_slope,
                "delta_auc_vs_slope": boot["delta_point"],
                "delta_auc_ci95": boot["delta_ci95"],
                "model_auc_ci95": boot["auc_ci95"],
            },
            "per_block": per_block,
            "frac_held_out_blocks_auc_gt_0_5": frac,
            "brier_informational": brier,
            "ece_informational": float(ece),
            "warn_near_constant_output": near_const,
            "n_test_pixels_subsampled": int(len(yt)),
        }

    report = {
        "status": "completed",
        "scientific_validation_status": "NOT_VALIDATED",
        "score_framing": "relative susceptibility rankings",
        "checkpoint_path": str(ckpt),
        "checkpoint_sha256": ckpt_hash,
        "data_hash": data_hash,
        "split_policy": (split_manifest or {}).get("policy")
        or "manifest_splits",
        "split_manifest": {
            "test": test_ids,
            "validation": val_ids,
            "train": list(splits.get("train") or []),
        },
        "seeds": seeds_note or [],
        "hazards": per_hazard,
        "limitations": default_limitations(),
        "notes": [
            "Evaluation uses held-out blocks only.",
            "ECE and Brier are informational only (not gates).",
            "Never claim validated risk, probability, or detection.",
        ],
    }
    return report
