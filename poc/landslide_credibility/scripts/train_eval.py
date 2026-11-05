"""Phase 3–4: nested spatial CV train, freeze, single test evaluation."""
from __future__ import annotations

import hashlib
import json
import pickle
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CONFIG,
    CORPUS,
    FEATURE_NAMES,
    OUT,
    PROTOCOL_V2,
    append_log,
    bootstrap_block,
    delta_auc_boot,
    ece,
    roc_auc,
    sha256_file,
    write_json,
)


def load_jsonl(path: Path) -> list[dict]:
    rows = []
    with path.open(encoding="utf-8") as f:
        for line in f:
            rows.append(json.loads(line))
    return rows


def matrix(rows: list[dict]) -> tuple[np.ndarray, np.ndarray, list[str], list[str]]:
    X = np.asarray([[r[f"f_{n}"] for n in FEATURE_NAMES] for r in rows], dtype=np.float64)
    y = np.asarray([r["y"] for r in rows], dtype=np.int32)
    blocks = [r["block"] for r in rows]
    ids = [r["sample_id"] for r in rows]
    # impute remaining nan with column median of finite
    for j in range(X.shape[1]):
        col = X[:, j]
        med = np.nanmedian(col)
        col[np.isnan(col)] = med if np.isfinite(med) else 0.0
        X[:, j] = col
    return X, y, blocks, ids


def pick_threshold(y: np.ndarray, s: np.ndarray) -> float:
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
            best_j, best_t = float(j), float(t)
    return best_t


def slope_scores(X: np.ndarray, train_idx: np.ndarray) -> np.ndarray:
    slope = X[:, FEATURE_NAMES.index("slope")]
    ref = np.sort(slope[train_idx])
    return np.searchsorted(ref, slope, side="right") / max(len(ref), 1)


def fit_logreg(X: np.ndarray, y: np.ndarray, seed: int):
    pipe = Pipeline(
        [
            ("scaler", StandardScaler()),
            ("clf", LogisticRegression(max_iter=3000, random_state=seed)),
        ]
    )
    pipe.fit(X, y)
    return pipe


def fit_hgb(X: np.ndarray, y: np.ndarray, seed: int):
    clf = HistGradientBoostingClassifier(
        max_depth=4,
        learning_rate=0.05,
        max_iter=150,
        random_state=seed,
    )
    clf.fit(X, y)
    return clf


def calibrate(model, X_val, y_val, method: str = "isotonic"):
    """Fit calibrator on validation predictions."""
    if hasattr(model, "predict_proba"):
        raw = model.predict_proba(X_val)[:, 1]
    else:
        raw = model.decision_function(X_val)
        raw = 1 / (1 + np.exp(-raw))
    # sklearn CalibratedClassifierCV needs estimator; use manual isotonic/platt on scores
    from sklearn.isotonic import IsotonicRegression
    from sklearn.linear_model import LogisticRegression as LR

    if method == "isotonic":
        iso = IsotonicRegression(out_of_bounds="clip")
        iso.fit(raw, y_val)
        return ("isotonic", iso)
    lr = LR(max_iter=1000)
    lr.fit(raw.reshape(-1, 1), y_val)
    return ("platt", lr)


def apply_cal(cal, scores: np.ndarray) -> np.ndarray:
    kind, obj = cal
    if kind == "isotonic":
        return np.clip(obj.predict(scores), 0, 1)
    return obj.predict_proba(scores.reshape(-1, 1))[:, 1]


def partial_dependence_slope(model, X_train: np.ndarray, n_grid: int = 20) -> dict:
    j = FEATURE_NAMES.index("slope")
    lo, hi = np.percentile(X_train[:, j], [10, 90])
    grid = np.linspace(lo, hi, n_grid)
    base = np.median(X_train, axis=0)
    preds = []
    for g in grid:
        X = np.tile(base, (1, 1))
        X = np.repeat(base.reshape(1, -1), 200, axis=0)
        X[:, j] = g
        # also vary other rows slightly from train sample
        idx = np.linspace(0, len(X_train) - 1, 200).astype(int)
        X = X_train[idx].copy()
        X[:, j] = g
        if hasattr(model, "predict_proba"):
            preds.append(float(model.predict_proba(X)[:, 1].mean()))
        else:
            preds.append(float(model.predict(X).mean()))
    diffs = np.diff(preds)
    return {
        "slope_grid": grid.tolist(),
        "mean_pred": preds,
        "nondecreasing": bool(np.all(diffs >= -1e-6)),
        "n_violations": int(np.sum(diffs < -1e-6)),
    }


def eval_candidate(
    name: str,
    y: np.ndarray,
    scores: np.ndarray,
    slope_s: np.ndarray,
    blocks: list[str],
    thr: float,
) -> dict:
    boot = bootstrap_block(y, scores, blocks, n_boot=1000, seed=42)
    delta = delta_auc_boot(y, scores, slope_s, blocks, n_boot=1000, seed=42)
    pred = (scores >= thr).astype(np.int32)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    hist, edges = np.histogram(scores, bins=np.linspace(0, 1, 21))
    per_block = {}
    for b in sorted(set(blocks)):
        idxs = [i for i, bb in enumerate(blocks) if bb == b]
        yy, ss = y[idxs], scores[idxs]
        per_block[b] = {"n": len(idxs), "n_pos": int(yy.sum()), "roc_auc": roc_auc(yy, ss)}
    both = [v for v in per_block.values() if v["n_pos"] > 0 and v["n"] - v["n_pos"] > 0]
    frac_gt = (
        sum(1 for v in both if v["roc_auc"] is not None and v["roc_auc"] > 0.5) / max(len(both), 1)
    )
    ci = delta.get("ci95")
    tier_a = bool(ci is not None and ci[0] > 0 and frac_gt >= 0.75)
    auc = boot["point"]["roc_auc"]
    ece_v = boot["point"]["ece"]
    near_const = bool(hist.max() / max(hist.sum(), 1) >= 0.95)
    tier_b = bool(tier_a and auc is not None and auc >= 0.80 and ece_v <= 0.10 and not near_const)
    return {
        "name": name,
        "metrics": boot,
        "vs_slope": delta,
        "threshold": thr,
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "per_block": per_block,
        "score_hist": {"counts": hist.tolist(), "edges": edges.tolist()},
        "tier_a": {
            "pass": tier_a,
            "A1_delta_ci_gt0": {"pass": bool(ci is not None and ci[0] > 0), "ci95": ci},
            "A2_frac_blocks": {"pass": frac_gt >= 0.75, "frac": frac_gt, "n_both": len(both)},
        },
        "tier_b": {
            "pass": tier_b,
            "auc_ge_0_80": {"pass": bool(auc is not None and auc >= 0.80), "auc": auc},
            "ece_le_0_10": {"pass": bool(ece_v is not None and ece_v <= 0.10), "ece": ece_v},
            "not_near_constant": {"pass": not near_const},
        },
    }


def run_scheme(scheme_path: Path, scheme_name: str) -> dict:
    rows = load_jsonl(scheme_path)
    X, y, blocks, ids = matrix(rows)
    split = np.asarray([r["split"] for r in rows])
    train_m = split == "train"
    val_m = split == "validation"
    test_m = split == "test"
    assert test_m.any() and train_m.any()

    seeds = CONFIG["seeds_train"]
    models_dir = CORPUS / "models"
    models_dir.mkdir(exist_ok=True)

    # Nested CV on train blocks for seed selection: pick seed with best mean val AUC among train LBO
    train_blocks = sorted(set(blocks[i] for i, m in enumerate(train_m) if m))

    def nested_score(fit_fn, seed: int) -> float:
        aucs = []
        for hold in train_blocks:
            tr = np.asarray(
                [train_m[i] and blocks[i] != hold for i in range(len(y))]
            )
            va = np.asarray(
                [train_m[i] and blocks[i] == hold for i in range(len(y))]
            )
            if tr.sum() < 10 or len(set(y[va])) < 2:
                continue
            m = fit_fn(X[tr], y[tr], seed)
            s = m.predict_proba(X[va])[:, 1]
            a = roc_auc(y[va], s)
            if a is not None:
                aucs.append(a)
        return float(np.mean(aucs)) if aucs else 0.0

    freeze = {"scheme": scheme_name, "candidates": {}, "frozen_at": datetime.now(timezone.utc).isoformat()}
    results = {"scheme": scheme_name, "n": len(rows), "splits": dict(zip(*np.unique(split, return_counts=True)))}

    # Slope baseline
    slope_s = slope_scores(X, np.where(train_m)[0])
    thr_slope = pick_threshold(y[train_m], slope_s[train_m])

    # Logreg: choose best seed by nested CV, refit on all train, calibrate on val
    seed_scores = {s: nested_score(fit_logreg, s) for s in seeds}
    best_seed_lr = max(seed_scores, key=seed_scores.get)
    lr = fit_logreg(X[train_m], y[train_m], best_seed_lr)
    cal_lr = calibrate(lr, X[val_m], y[val_m], "isotonic") if val_m.sum() >= 10 and len(set(y[val_m])) > 1 else None
    raw_lr = lr.predict_proba(X)[:, 1]
    scores_lr = apply_cal(cal_lr, raw_lr) if cal_lr else raw_lr
    thr_lr = pick_threshold(y[train_m], scores_lr[train_m])
    path_lr = models_dir / f"{scheme_name}_logreg.pkl"
    with path_lr.open("wb") as f:
        pickle.dump({"model": lr, "cal": cal_lr, "seed": best_seed_lr, "thr": thr_lr}, f)
    freeze["candidates"]["B2_logreg"] = {
        "path": str(path_lr),
        "sha256": sha256_file(path_lr),
        "seed": best_seed_lr,
        "nested_seed_scores": seed_scores,
        "threshold": thr_lr,
    }

    seed_scores_h = {s: nested_score(fit_hgb, s) for s in seeds}
    best_seed_h = max(seed_scores_h, key=seed_scores_h.get)
    hgb = fit_hgb(X[train_m], y[train_m], best_seed_h)
    cal_h = calibrate(hgb, X[val_m], y[val_m], "isotonic") if val_m.sum() >= 10 and len(set(y[val_m])) > 1 else None
    raw_h = hgb.predict_proba(X)[:, 1]
    scores_h = apply_cal(cal_h, raw_h) if cal_h else raw_h
    thr_h = pick_threshold(y[train_m], scores_h[train_m])
    path_h = models_dir / f"{scheme_name}_hgb.pkl"
    with path_h.open("wb") as f:
        pickle.dump({"model": hgb, "cal": cal_h, "seed": best_seed_h, "thr": thr_h}, f)
    freeze["candidates"]["B3_hgb"] = {
        "path": str(path_h),
        "sha256": sha256_file(path_h),
        "seed": best_seed_h,
        "nested_seed_scores": seed_scores_h,
        "threshold": thr_h,
    }

    # Plausibility on train
    freeze["partial_dependence_slope_logreg"] = partial_dependence_slope(lr, X[train_m])
    freeze["partial_dependence_slope_hgb"] = partial_dependence_slope(hgb, X[train_m])

    # FREEZE before opening test
    freeze_path = OUT / f"phase3_freeze_{scheme_name}.json"
    write_json(freeze_path, freeze)
    append_log(f"FROZE candidates scheme={scheme_name} before test eval")

    # Single test evaluation
    y_te = y[test_m]
    b_te = [blocks[i] for i, m in enumerate(test_m) if m]
    slope_te = slope_s[test_m]
    evals = {
        "B1_slope": eval_candidate("B1_slope", y_te, slope_s[test_m], slope_te, b_te, thr_slope),
        "B2_logreg": eval_candidate("B2_logreg", y_te, scores_lr[test_m], slope_te, b_te, thr_lr),
        "B3_hgb": eval_candidate("B3_hgb", y_te, scores_h[test_m], slope_te, b_te, thr_h),
    }
    results["freeze_path"] = str(freeze_path)
    results["evaluation"] = evals
    results["n_test"] = int(test_m.sum())
    results["n_train"] = int(train_m.sum())
    results["n_val"] = int(val_m.sum())
    return results


def main() -> int:
    append_log("START train_eval")
    near = CORPUS / "samples_near.jsonl"
    far = CORPUS / "samples_far.jsonl"
    if not near.exists():
        write_json(OUT / "phase4_eval.json", {"status": "BLOCKED", "reason": "corpus missing"})
        return 2
    protocol_sha = sha256_file(PROTOCOL_V2)
    out = {
        "protocol_v2_sha256": protocol_sha,
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    print("Evaluating NEAR (primary)...", flush=True)
    out["NEAR"] = run_scheme(near, "NEAR")
    if far.exists():
        print("Evaluating FAR (secondary)...", flush=True)
        out["FAR"] = run_scheme(far, "FAR")
    write_json(OUT / "phase3_freeze.json", {
        "NEAR": out["NEAR"].get("freeze_path"),
        "FAR": out.get("FAR", {}).get("freeze_path"),
        "protocol_v2_sha256": protocol_sha,
    })
    write_json(OUT / "phase4_eval.json", out)
    # print summary
    for scheme in ("NEAR", "FAR"):
        if scheme not in out:
            continue
        print(f"=== {scheme} ===", flush=True)
        for name, rec in out[scheme]["evaluation"].items():
            print(
                name,
                "TierA",
                rec["tier_a"]["pass"],
                "TierB",
                rec["tier_b"]["pass"],
                "auc",
                rec["metrics"]["point"]["roc_auc"],
                "dci",
                rec["vs_slope"]["ci95"],
                flush=True,
            )
    append_log("END train_eval")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
