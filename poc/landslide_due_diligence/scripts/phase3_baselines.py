"""Phase 3: tile-level baselines on existing FeatureStacks v3 (diagnostic)."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import torch
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CHANNEL_NAMES,
    FEATURESTACKS,
    FOUNDATION_V2,
    NODATA,
    OUT,
    PROTOCOL,
    REPO,
    SPECTRAL_IDX,
    TERRAIN_IDX,
    append_run_log,
    block5,
    bootstrap_block_metrics,
    delta_auc_bootstrap,
    ece,
    pr_auc,
    roc_auc,
    sha256_file,
    write_json,
)

sys.path.insert(0, str(REPO / "model" / "src"))


def load_tiles() -> list[dict]:
    manifest = json.loads((FEATURESTACKS / "manifest.json").read_text(encoding="utf-8"))
    split_of = {}
    for split, ids in (manifest.get("splits") or {}).items():
        for sid in ids:
            split_of[sid] = split
    tiles = []
    for d in sorted((FEATURESTACKS / "samples").iterdir()):
        if not d.is_dir():
            continue
        meta = json.loads((d / "metadata.json").read_text(encoding="utf-8"))
        lat, lon = meta.get("latitude"), meta.get("longitude")
        if lat is None:
            b = meta["bbox_wgs84"]
            lon = (b[0] + b[2]) / 2
            lat = (b[1] + b[3]) / 2
        arr = np.load(d / "feature_stack.npy").astype(np.float64)
        y = 1 if (meta.get("labels") or {}).get("landslide") == 1 else 0
        feats = []
        for i in TERRAIN_IDX + [11, 12]:  # terrain + gravity + magnetics
            ch = arr[i]
            finite = ch[ch != NODATA]
            if finite.size == 0:
                feats.extend([np.nan, np.nan, np.nan])
            else:
                feats.extend(
                    [float(np.mean(finite)), float(np.std(finite)), float(np.percentile(finite, 90))]
                )
        slope = arr[1]
        sf = slope[slope != NODATA]
        mean_slope = float(np.mean(sf)) if sf.size else 0.0
        tiles.append(
            {
                "sample_id": d.name,
                "y": y,
                "split": split_of.get(d.name, "unknown"),
                "block5": block5(float(lat), float(lon)),
                "mean_slope": mean_slope,
                "x_terrain": np.asarray(feats, dtype=np.float64),
                "arr": arr,
            }
        )
    return tiles


def tile_label_from_multitask(sample_dir: Path) -> int:
    lab = np.load(sample_dir / "labels_multitask.npz")
    # presence if any positive landslide pixel with mask
    t = lab["landslide"]
    m = lab["landslide_mask"]
    return 1 if np.logical_and(t > 0.5, m > 0.5).any() else 0


def foundation_scores(tiles: list[dict], zero_spectral: bool) -> np.ndarray:
    """Score tiles with foundation v2 using the checkpoint's stored normalization.

    Matches ``train_foundation_multitask.FeatureStackDataset``: only non-finite
    values are replaced; ``-9999`` nodata is left as-is (as in original training).
    """
    from ssri_model.architecture.config import SSRIModelConfig
    from ssri_model.architecture.multitask import SSRIMultiTaskModel

    device = torch.device("cpu")
    ckpt = torch.load(FOUNDATION_V2, map_location=device, weights_only=False)
    state = ckpt["state_dict"]
    cfg = SSRIModelConfig(**ckpt["config"]) if isinstance(ckpt.get("config"), dict) else SSRIModelConfig()
    model = SSRIMultiTaskModel(cfg, dann=False).to(device)
    model.load_state_dict(state, strict=True)
    model.eval()

    mean = np.asarray(ckpt["normalization"]["mean"], dtype=np.float32).reshape(-1, 1, 1)
    std = np.asarray(ckpt["normalization"]["std"], dtype=np.float32).reshape(-1, 1, 1)
    std = np.maximum(std, 1e-6)
    th = tw = int(ckpt.get("spatial_size") or 64)

    scores = []
    with torch.no_grad():
        for t in tiles:
            a = t["arr"].astype(np.float32).copy()
            if zero_spectral:
                # Ablation: replace spectral with training mean so channel is constant null signal
                for i in SPECTRAL_IDX:
                    a[i] = float(mean[i, 0, 0])
            for c in range(a.shape[0]):
                band = a[c]
                bad = ~np.isfinite(band)
                if bad.any():
                    band = band.copy()
                    band[bad] = float(mean[c, 0, 0])
                    a[c] = band
                a[c] = (a[c] - mean[c, 0, 0]) / std[c, 0, 0]
            c, h, w = a.shape
            out = np.zeros((c, th, tw), dtype=np.float32)
            src_y0 = max(0, (h - th) // 2)
            src_x0 = max(0, (w - tw) // 2)
            dy = min(h - src_y0, th)
            dx = min(w - src_x0, tw)
            dst_y0 = (th - dy) // 2
            dst_x0 = (tw - dx) // 2
            out[:, dst_y0 : dst_y0 + dy, dst_x0 : dst_x0 + dx] = a[
                :, src_y0 : src_y0 + dy, src_x0 : src_x0 + dx
            ]
            x = torch.from_numpy(out[None, ...])
            logit = model(x)["landslide"]
            prob = torch.sigmoid(logit).cpu().numpy()[0]
            scores.append(float(np.mean(prob)))
    return np.asarray(scores, dtype=np.float64)


def pick_threshold(y: np.ndarray, s: np.ndarray) -> float:
    """Maximize Youden J on training scores."""
    best_t, best_j = 0.5, -1.0
    for t in np.linspace(0.05, 0.95, 37):
        pred = (s >= t).astype(np.int32)
        tp = ((pred == 1) & (y == 1)).sum()
        tn = ((pred == 0) & (y == 0)).sum()
        fp = ((pred == 1) & (y == 0)).sum()
        fn = ((pred == 0) & (y == 1)).sum()
        tpr = tp / max(tp + fn, 1)
        fpr = fp / max(fp + tn, 1)
        j = tpr - fpr
        if j > best_j:
            best_j, best_t = j, float(t)
    return best_t


def metrics_bundle(y, s, blocks, thr) -> dict:
    boot = bootstrap_block_metrics(y, s, blocks, n_boot=1000, seed=42)
    pred = (s >= thr).astype(np.int32)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    prec = tp / max(tp + fp, 1)
    rec = tp / max(tp + fn, 1)
    f1 = 2 * prec * rec / max(prec + rec, 1e-12)
    # per-block auc
    uniq = sorted(set(blocks))
    per_block = {}
    for b in uniq:
        idxs = [i for i, bb in enumerate(blocks) if bb == b]
        yy, ss = y[idxs], s[idxs]
        per_block[b] = {
            "n": len(idxs),
            "n_pos": int(yy.sum()),
            "roc_auc": roc_auc(yy, ss),
        }
    hist, edges = np.histogram(s, bins=np.linspace(0, 1, 21))
    return {
        **boot,
        "threshold": thr,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "precision": prec,
        "recall": rec,
        "f1": f1,
        "per_block": per_block,
        "score_hist_counts": hist.tolist(),
        "score_hist_edges": edges.tolist(),
        "near_constant_fail": bool(hist.max() / max(hist.sum(), 1) >= 0.95),
    }


def apply_acceptance(name: str, cand: dict, delta: dict) -> dict:
    auc = cand["point"]["roc_auc"]
    ece_v = cand["point"]["ece"]
    per = cand["per_block"]
    both = [v for v in per.values() if v["n_pos"] > 0 and v["n"] - v["n_pos"] > 0]
    above = sum(1 for v in both if v["roc_auc"] is not None and v["roc_auc"] > 0.5)
    frac = above / max(len(both), 1)
    ci = delta.get("ci95")
    a = ci is not None and ci[0] > 0
    b = auc is not None and auc >= 0.80
    c = ece_v is not None and ece_v <= 0.10
    d = not cand["near_constant_fail"]
    e = frac >= 0.75 if both else False
    return {
        "candidate": name,
        "A_delta_auc_ci_gt0": {"pass": a, "ci95": ci, "point_delta": delta.get("delta_roc_auc_point")},
        "B_auc_ge_0_80": {"pass": b, "auc": auc},
        "C_ece_le_0_10": {"pass": c, "ece": ece_v},
        "D_not_near_constant": {"pass": d},
        "E_per_block_auc": {"pass": e, "frac_blocks_auc_gt_0_5": frac, "n_both_class_blocks": len(both)},
        "PASS_ALL": bool(a and b and c and d and e),
    }


def main() -> int:
    append_run_log(f"{datetime.now(timezone.utc).isoformat()} START phase3_baselines")
    protocol_sha = sha256_file(PROTOCOL)
    tiles = load_tiles()
    # prefer multitask npz labels when present
    for t in tiles:
        p = FEATURESTACKS / "samples" / t["sample_id"]
        if (p / "labels_multitask.npz").exists():
            t["y"] = tile_label_from_multitask(p)

    y = np.asarray([t["y"] for t in tiles], dtype=np.int32)
    blocks = [t["block5"] for t in tiles]
    splits = [t["split"] for t in tiles]
    train_m = np.asarray([s in ("train", "validation") for s in splits])  # tune on train+val
    test_m = np.asarray([s == "test" for s in splits])

    # Also evaluate on full set with block bootstrap for CI honesty given tiny test
    results = {
        "phase": 3,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "protocol_sha256": protocol_sha,
        "foundation_ckpt_sha256": sha256_file(FOUNDATION_V2),
        "n_tiles": len(tiles),
        "prevalence": float(y.mean()),
        "n_test": int(test_m.sum()),
        "n_trainval": int(train_m.sum()),
        "sample_size_note": (
            "n=240 total, test≈28 — BELOW PROTOCOL minima for GO-LIMITED. "
            "Phase 3 is diagnostic only."
        ),
        "predict_all_positive_pixel_f1_reference": None,
    }

    # pixel prevalence reference from test multitask labels
    tp = fp = fn = tn = 0
    for t, is_te in zip(tiles, test_m):
        if not is_te:
            continue
        p = FEATURESTACKS / "samples" / t["sample_id"]
        if not (p / "labels_multitask.npz").exists():
            continue
        lab = np.load(p / "labels_multitask.npz")
        gt = (lab["landslide"] > 0.5) & (lab["landslide_mask"] > 0.5)
        # predict all positive on masked pixels
        m = lab["landslide_mask"] > 0.5
        pred = np.ones_like(gt)
        tp += int((pred & gt & m).sum())
        fp += int((pred & ~gt & m).sum())
        fn += 0
        tn += 0
    if tp + fp:
        prec = tp / (tp + fp)
        rec = 1.0
        results["predict_all_positive_pixel_f1_reference"] = {
            "precision": prec,
            "recall": rec,
            "f1": 2 * prec * rec / (prec + rec),
            "note": "On masked test pixels; illustrates why pixel F1 is not primary",
        }

    scores: dict[str, np.ndarray] = {}
    thresholds: dict[str, float] = {}

    # B1 slope
    slope_s = np.asarray([t["mean_slope"] for t in tiles], dtype=np.float64)
    # normalize slope to 0-1 via train ranks for ECE-ish scores
    tr_slope = slope_s[train_m]
    # score = empirical CDF on train
    def cdf_score(raw, ref):
        return np.searchsorted(np.sort(ref), raw, side="right") / max(len(ref), 1)

    scores["B1_slope"] = cdf_score(slope_s, tr_slope)
    thresholds["B1_slope"] = pick_threshold(y[train_m], scores["B1_slope"][train_m])

    # B2 / B3
    X = np.stack([t["x_terrain"] for t in tiles], axis=0)
    # impute nan with train column mean
    col_mean = np.nanmean(X[train_m], axis=0)
    inds = np.where(np.isnan(X))
    X = X.copy()
    X[inds] = np.take(col_mean, inds[1])

    logreg = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=2000, random_state=42)),
        ]
    )
    logreg.fit(X[train_m], y[train_m])
    scores["B2_logreg"] = logreg.predict_proba(X)[:, 1]
    thresholds["B2_logreg"] = pick_threshold(y[train_m], scores["B2_logreg"][train_m])

    gbm = HistGradientBoostingClassifier(max_depth=3, learning_rate=0.05, max_iter=100, random_state=42)
    gbm.fit(X[train_m], y[train_m])
    scores["B3_hgb"] = gbm.predict_proba(X)[:, 1]
    thresholds["B3_hgb"] = pick_threshold(y[train_m], scores["B3_hgb"][train_m])

    print("running foundation intact...", flush=True)
    scores["B4_unet"] = foundation_scores(tiles, zero_spectral=False)
    thresholds["B4_unet"] = pick_threshold(y[train_m], scores["B4_unet"][train_m])
    print("running foundation spectral-zeroed...", flush=True)
    scores["B5_unet_spectral0"] = foundation_scores(tiles, zero_spectral=True)
    thresholds["B5_unet_spectral0"] = pick_threshold(
        y[train_m], scores["B5_unet_spectral0"][train_m]
    )

    # Evaluate on TEST tiles with block bootstrap; also report trainval for transparency
    def eval_split(mask: np.ndarray, label: str) -> dict:
        yy = y[mask]
        bb = [blocks[i] for i, m in enumerate(mask) if m]
        out = {}
        slope_s_m = scores["B1_slope"][mask]
        for name, s_all in scores.items():
            ss = s_all[mask]
            thr = thresholds[name]
            bundle = metrics_bundle(yy, ss, bb, thr)
            delta = delta_auc_bootstrap(yy, ss, slope_s_m, bb, n_boot=1000, seed=42)
            acc = apply_acceptance(name, bundle, delta)
            out[name] = {"metrics": bundle, "vs_slope": delta, "acceptance": acc}
        # majority references
        out["B0_always_neg"] = {
            "roc_auc": None,
            "note": "constant score 0 — ROC undefined or chance; not a ranking model",
        }
        out["B0_always_pos_prevalence"] = {
            "tile_prevalence": float(yy.mean()),
            "note": "constant positive predictions; ranking metrics undefined",
        }
        return out

    results["eval_test_manifest"] = eval_split(test_m, "test")
    results["eval_all_tiles_diagnostic"] = eval_split(
        np.ones(len(tiles), dtype=bool), "all"
    )
    results["thresholds_frozen_on_trainval"] = thresholds
    results["runs"] = [
        {"name": k, "seed": 42, "status": "ok"} for k in scores
    ]

    write_json(OUT / "phase3_baselines.json", results)
    append_run_log(f"{datetime.now(timezone.utc).isoformat()} END phase3_baselines")
    # print brief
    for name, rec in results["eval_test_manifest"].items():
        if "acceptance" not in rec:
            continue
        a = rec["acceptance"]
        print(
            name,
            "PASS_ALL" if a["PASS_ALL"] else "FAIL",
            "auc",
            a["B_auc_ge_0_80"]["auc"],
            "delta_ci",
            a["A_delta_auc_ci_gt0"]["ci95"],
            flush=True,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
