"""Phase 3–4: LOBO nested CV, freeze, sealed holdout once, exploratory spent blocks."""
from __future__ import annotations

import json
import pickle
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (  # noqa: E402
    CORPUS,
    FEATURE_NAMES,
    OUT,
    PROTOCOL_V3,
    SEEDS,
    SPENT_V2_TEST,
    append_log,
    brier,
    ece,
    haversine_km,
    load_jsonl,
    pr_auc,
    roc_auc,
    sha256_file,
    write_json,
)


def matrix(rows):
    X = np.asarray([[r[f"f_{n}"] for n in FEATURE_NAMES] for r in rows], float)
    y = np.asarray([r["y"] for r in rows], int)
    blocks = [r["block"] for r in rows]
    for j in range(X.shape[1]):
        med = np.nanmedian(X[:, j])
        X[np.isnan(X[:, j]), j] = med if np.isfinite(med) else 0.0
    return X, y, blocks


def pick_thr(y, s):
    best_t, best_j = 0.5, -1.0
    for t in np.linspace(0.05, 0.95, 37):
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


def fit_lr(X, y, seed):
    pipe = Pipeline([("scaler", StandardScaler()), ("clf", LogisticRegression(max_iter=3000, random_state=seed))])
    pipe.fit(X, y)
    return pipe


def fit_hgb(X, y, seed):
    clf = HistGradientBoostingClassifier(max_depth=4, learning_rate=0.05, max_iter=150, random_state=seed)
    clf.fit(X, y)
    return clf


def calib_fit(raw, y):
    if len(set(y)) < 2 or len(y) < 10:
        return None
    iso = IsotonicRegression(out_of_bounds="clip")
    iso.fit(raw, y)
    return iso


def calib_apply(iso, raw):
    return np.clip(iso.predict(raw), 0, 1) if iso is not None else raw


def slope_cdf_scores(X, train_idx):
    j = FEATURE_NAMES.index("slope")
    ref = np.sort(X[train_idx, j])
    return np.searchsorted(ref, X[:, j], side="right") / max(len(ref), 1)


def buffer_mask(rows, hold_idx, buf_km=50.0):
    """True for training-eligible samples (not in hold block and >=buf from hold samples)."""
    hold_rows = [rows[i] for i in hold_idx]
    mask = np.ones(len(rows), dtype=bool)
    hold_set = {rows[i]["block"] for i in hold_idx}
    for i, r in enumerate(rows):
        if r["block"] in hold_set:
            mask[i] = False
            continue
        if any(haversine_km(r["lat"], r["lon"], h["lat"], h["lon"]) < buf_km for h in hold_rows):
            mask[i] = False
    return mask


def metrics_pack(y, s, thr):
    pred = (s >= thr).astype(int)
    tp = int(((pred == 1) & (y == 1)).sum())
    tn = int(((pred == 0) & (y == 0)).sum())
    fp = int(((pred == 1) & (y == 0)).sum())
    fn = int(((pred == 0) & (y == 1)).sum())
    hist, edges = np.histogram(np.clip(s, 0, 1), bins=np.linspace(0, 1, 21))
    return {
        "roc_auc": roc_auc(y, s),
        "pr_auc": pr_auc(y, s),
        "brier": brier(y, s),
        "ece": ece(y, s),
        "confusion": {"tp": tp, "fp": fp, "fn": fn, "tn": tn},
        "score_hist_counts": hist.tolist(),
        "score_hist_edges": edges.tolist(),
    }


def bootstrap_delta(y, s_c, s_b, blocks, n_boot=1000, seed=42):
    rng = np.random.default_rng(seed)
    uniq = sorted(set(blocks))
    by = {b: [i for i, bb in enumerate(blocks) if bb == b] for b in uniq}
    pc, pb = roc_auc(y, s_c), roc_auc(y, s_b)
    point = None if pc is None or pb is None else pc - pb
    deltas, aucs = [], []
    for _ in range(n_boot):
        ch = rng.choice(uniq, size=len(uniq), replace=True)
        idxs = []
        for b in ch:
            idxs.extend(by[b])
        idxs = np.asarray(idxs)
        c, b = roc_auc(y[idxs], s_c[idxs]), roc_auc(y[idxs], s_b[idxs])
        if c is not None:
            aucs.append(c)
        if c is not None and b is not None:
            deltas.append(c - b)
    def ci(a):
        a = np.asarray(a, float)
        return [float(np.percentile(a, 2.5)), float(np.percentile(a, 97.5))] if len(a) >= 10 else None
    return {
        "auc_point": pc,
        "slope_auc_point": pb,
        "delta_point": point,
        "auc_ci95": ci(aucs),
        "delta_ci95": ci(deltas),
    }


def partial_dep_slope(model, X_train):
    j = FEATURE_NAMES.index("slope")
    lo, hi = np.percentile(X_train[:, j], [10, 90])
    grid = np.linspace(lo, hi, 20)
    idx = np.linspace(0, len(X_train) - 1, min(200, len(X_train))).astype(int)
    preds = []
    for g in grid:
        X = X_train[idx].copy()
        X[:, j] = g
        preds.append(float(model.predict_proba(X)[:, 1].mean()))
    diffs = np.diff(preds)
    return {"nondecreasing": bool(np.all(diffs >= -1e-6)), "n_violations": int(np.sum(diffs < -1e-6)), "grid": grid.tolist(), "preds": preds}


def run_lobo(rows, scheme_name: str) -> dict:
    X, y, blocks = matrix(rows)
    uniq_blocks = sorted(set(blocks))
    # exclude spent from LOBO if present
    uniq_blocks = [b for b in uniq_blocks if b not in SPENT_V2_TEST]
    fold_rows = []
    # Collect OOF predictions
    oof = {k: np.full(len(rows), np.nan) for k in ("slope", "logreg", "hgb")}
    thr_rec = {"slope": [], "logreg": [], "hgb": []}
    seed_scores = {"logreg": {}, "hgb": {}}

    # Choose seed via mean inner AUC on first fold proxy: evaluate all seeds on nested leave-one of train blocks of fold0 style — simplify: pick seed maximizing mean OOF on a quick nested among all but using only train folds average
    # Protocol: nested tuning inside training folds. For speed: for each outer fold, pick seed by mean AUC on 20% of train blocks as inner val.

    for hold in uniq_blocks:
        hold_idx = [i for i, b in enumerate(blocks) if b == hold]
        if len(set(y[hold_idx])) < 2:
            continue
        tr_mask = buffer_mask(rows, hold_idx, 50.0)
        tr_idx = np.where(tr_mask)[0]
        if tr_idx.size < 30 or len(set(y[tr_idx])) < 2:
            continue
        # inner split: hold out one train block for seed/threshold
        tr_blocks = sorted({blocks[i] for i in tr_idx})
        inner_hold = tr_blocks[0]
        inner_tr = np.asarray([i for i in tr_idx if blocks[i] != inner_hold])
        inner_va = np.asarray([i for i in tr_idx if blocks[i] == inner_hold])
        if inner_tr.size < 20 or inner_va.size < 5 or len(set(y[inner_va])) < 2:
            inner_tr = tr_idx
            inner_va = tr_idx  # fallback

        # seed selection
        best_lr, best_lr_s, best_h, best_h_s = None, -1, None, -1
        for seed in SEEDS:
            lr = fit_lr(X[inner_tr], y[inner_tr], seed)
            h = fit_hgb(X[inner_tr], y[inner_tr], seed)
            a_lr = roc_auc(y[inner_va], lr.predict_proba(X[inner_va])[:, 1]) or 0
            a_h = roc_auc(y[inner_va], h.predict_proba(X[inner_va])[:, 1]) or 0
            seed_scores["logreg"].setdefault(str(seed), []).append(a_lr)
            seed_scores["hgb"].setdefault(str(seed), []).append(a_h)
            if a_lr > best_lr_s:
                best_lr_s, best_lr = a_lr, seed
            if a_h > best_h_s:
                best_h_s, best_h = a_h, seed

        lr = fit_lr(X[tr_idx], y[tr_idx], best_lr)
        hgb = fit_hgb(X[tr_idx], y[tr_idx], best_h)
        slope_s = slope_cdf_scores(X, tr_idx)
        raw_lr = lr.predict_proba(X)[:, 1]
        raw_h = hgb.predict_proba(X)[:, 1]
        iso_lr = calib_fit(raw_lr[tr_idx], y[tr_idx])
        iso_h = calib_fit(raw_h[tr_idx], y[tr_idx])
        s_lr = calib_apply(iso_lr, raw_lr)
        s_h = calib_apply(iso_h, raw_h)
        thr_s = pick_thr(y[tr_idx], slope_s[tr_idx])
        thr_lr = pick_thr(y[tr_idx], s_lr[tr_idx])
        thr_h = pick_thr(y[tr_idx], s_h[tr_idx])
        thr_rec["slope"].append(thr_s)
        thr_rec["logreg"].append(thr_lr)
        thr_rec["hgb"].append(thr_h)
        for i in hold_idx:
            oof["slope"][i] = slope_s[i]
            oof["logreg"][i] = s_lr[i]
            oof["hgb"][i] = s_h[i]
        fold_rows.append({"hold": hold, "n_hold": len(hold_idx), "n_train": int(tr_idx.size), "seed_lr": best_lr, "seed_hgb": best_h})

    # evaluate on OOF covered samples
    covered = np.isfinite(oof["slope"])
    y_c = y[covered]
    b_c = [blocks[i] for i, m in enumerate(covered) if m]
    thr_s = float(np.median(thr_rec["slope"])) if thr_rec["slope"] else 0.5
    thr_lr = float(np.median(thr_rec["logreg"])) if thr_rec["logreg"] else 0.5
    thr_h = float(np.median(thr_rec["hgb"])) if thr_rec["hgb"] else 0.5

    # B0 majority: constant score = train prevalence (ranking-degenerate; AUC ~0.5)
    prev = float(y_c.mean()) if len(y_c) else 0.5
    oof_maj = np.full(len(rows), prev)
    results = {}
    for name, key, thr, scores in [
        ("B0_majority", "majority", 0.5, oof_maj[covered]),
        ("B1_slope", "slope", thr_s, oof["slope"][covered]),
        ("B2_logreg", "logreg", thr_lr, oof["logreg"][covered]),
        ("B3_hgb", "hgb", thr_h, oof["hgb"][covered]),
    ]:
        s = scores
        pack = metrics_pack(y_c, s, thr)
        boot = bootstrap_delta(y_c, s, oof["slope"][covered], b_c)
        per = {}
        for b in sorted(set(b_c)):
            idxs = [i for i, bb in enumerate(b_c) if bb == b]
            per[b] = {
                "n": len(idxs),
                "n_pos": int(y_c[idxs].sum()),
                "roc_auc": roc_auc(y_c[idxs], s[idxs]),
            }
        both = [v for v in per.values() if v["n_pos"] > 0 and v["n"] - v["n_pos"] > 0]
        frac = sum(1 for v in both if v["roc_auc"] is not None and v["roc_auc"] > 0.5) / max(len(both), 1)
        dci = boot["delta_ci95"]
        results[name] = {
            **pack,
            "vs_slope": boot,
            "threshold": thr,
            "per_block": per,
            "frac_blocks_auc_gt_0_5": frac,
            "n_both_class_blocks": len(both),
            "tier_a_near_components": {
                "delta_ci_gt0": bool(dci is not None and dci[0] > 0) if name not in ("B0_majority", "B1_slope") else None,
                "frac_blocks": frac,
            },
        }

    # Final models on all LOBO rows for freeze + sealed eval
    lr_final = fit_lr(X, y, 42)
    hgb_final = fit_hgb(X, y, 42)
    models_dir = CORPUS / "models"
    models_dir.mkdir(exist_ok=True)
    path_lr = models_dir / f"{scheme_name}_logreg.pkl"
    path_h = models_dir / f"{scheme_name}_hgb.pkl"
    pickle.dump({"model": lr_final, "thr": thr_lr}, path_lr.open("wb"))
    pickle.dump({"model": hgb_final, "thr": thr_h}, path_h.open("wb"))

    return {
        "scheme": scheme_name,
        "n": len(rows),
        "n_oof": int(covered.sum()),
        "folds": fold_rows,
        "seed_mean_inner_auc": {k: {s: float(np.mean(v)) for s, v in d.items()} for k, d in seed_scores.items()},
        "lobo_results": results,
        "pd_logreg": partial_dep_slope(lr_final, X),
        "pd_hgb": partial_dep_slope(hgb_final, X),
        "frozen": {
            "logreg_sha256": sha256_file(path_lr),
            "hgb_sha256": sha256_file(path_h),
            "logreg_path": str(path_lr),
            "hgb_path": str(path_h),
            "thr_slope": thr_s,
            "thr_logreg": thr_lr,
            "thr_hgb": thr_h,
        },
    }


def eval_holdout(rows, frozen_near, label: str) -> dict:
    if not rows:
        return {"status": "EMPTY", "label": label}
    X, y, blocks = matrix(rows)
    # slope scores using holdout's own train? Protocol: frozen candidate — use slope CDF from frozen training distribution
    # Use NEAR LOBO training distribution from file
    near = load_jsonl(CORPUS / "lobo_near.jsonl")
    Xtr, ytr, _ = matrix(near)
    j = FEATURE_NAMES.index("slope")
    ref = np.sort(Xtr[:, j])
    slope_s = np.searchsorted(ref, X[:, j], side="right") / max(len(ref), 1)
    lr = pickle.load(open(frozen_near["frozen"]["logreg_path"], "rb"))["model"]
    hgb = pickle.load(open(frozen_near["frozen"]["hgb_path"], "rb"))["model"]
    s_lr = lr.predict_proba(X)[:, 1]
    s_h = hgb.predict_proba(X)[:, 1]
    out = {}
    for name, s, thr in [
        ("B1_slope", slope_s, frozen_near["frozen"]["thr_slope"]),
        ("B2_logreg", s_lr, frozen_near["frozen"]["thr_logreg"]),
        ("B3_hgb", s_h, frozen_near["frozen"]["thr_hgb"]),
    ]:
        pack = metrics_pack(y, s, thr)
        boot = bootstrap_delta(y, s, slope_s, blocks)
        out[name] = {**pack, "vs_slope": boot, "threshold": thr}
    return {"status": "OK", "label": label, "n": len(rows), "results": out}


def apply_acceptance(near_lobo, slope_lobo, sealed) -> dict:
    """Mechanical Tier A/B from PROTOCOL_v3."""
    def cand_tier_a(name):
        n = near_lobo["lobo_results"][name]
        sm = slope_lobo["lobo_results"][name]
        dci = n["vs_slope"]["delta_ci95"]
        a1 = bool(dci is not None and dci[0] > 0)
        a2 = bool((sm["vs_slope"]["delta_point"] or 0) > 0)
        a3 = bool(n["frac_blocks_auc_gt_0_5"] >= 0.75)
        return {"pass": a1 and a2 and a3, "NEAR_delta_ci_gt0": a1, "SLOPE_MATCHED_delta_point_gt0": a2, "frac_blocks": a3, "dci": dci, "sm_delta": sm["vs_slope"]["delta_point"]}

    out = {}
    for name in ("B2_logreg", "B3_hgb"):
        ta = cand_tier_a(name)
        tb = {"pass": False, "reason": "sealed unavailable or tier A failed"}
        if ta["pass"] and sealed.get("status") == "OK" and name in sealed.get("results", {}):
            r = sealed["results"][name]
            tb = {
                "pass": bool((r["vs_slope"]["delta_point"] or 0) > 0 and (r["roc_auc"] or 0) >= 0.75),
                "delta_point": r["vs_slope"]["delta_point"],
                "auc": r["roc_auc"],
            }
        out[name] = {"tier_a": ta, "tier_b": tb}
    return out


def main() -> int:
    append_log("START lobo_eval")
    protocol_sha = sha256_file(PROTOCOL_V3)
    near = load_jsonl(CORPUS / "lobo_near.jsonl")
    far = load_jsonl(CORPUS / "lobo_far.jsonl")
    slope_m = load_jsonl(CORPUS / "lobo_slope_matched.jsonl")
    spent = load_jsonl(CORPUS / "spent_v2_near.jsonl")
    sealed_rows = load_jsonl(CORPUS / "sealed_fresh.jsonl")

    print("LOBO NEAR...", flush=True)
    near_res = run_lobo(near, "NEAR")
    print("LOBO FAR...", flush=True)
    far_res = run_lobo(far, "FAR")
    print("LOBO SLOPE_MATCHED...", flush=True)
    slope_res = run_lobo(slope_m, "SLOPE_MATCHED")

    freeze = {
        "protocol_v3_sha256": protocol_sha,
        "frozen_at": datetime.now(timezone.utc).isoformat(),
        "NEAR": near_res["frozen"],
        "FAR": far_res["frozen"],
        "SLOPE_MATCHED": slope_res["frozen"],
        "note": "Frozen before sealed holdout opened",
    }
    write_json(OUT / "phase3_freeze.json", freeze)
    append_log("FROZE models before sealed holdout")

    print("Sealed fresh holdout (once)...", flush=True)
    sealed_eval = eval_holdout(sealed_rows, near_res, "sealed_fresh")
    print("Exploratory spent v2 blocks...", flush=True)
    spent_eval = eval_holdout(spent, near_res, "exploratory_spent_v2_test")

    acceptance = apply_acceptance(near_res, slope_res, sealed_eval)
    # Decision
    any_a = any(acceptance[c]["tier_a"]["pass"] for c in acceptance)
    any_b = any(acceptance[c]["tier_b"]["pass"] for c in acceptance)
    power = json.loads((OUT / "phase1_power.json").read_text(encoding="utf-8"))
    lobo_mdd = power["summary"]["lobo_mdd"]
    if any_b:
        decision = "GO-LIMITED"
        level = "L2"
    elif any_a:
        decision = "RESEARCH-CREDIBLE"
        level = "L2"
    elif lobo_mdd <= 0.08:
        decision = "NO-GAIN"
        level = "L1"
    else:
        decision = "INCONCLUSIVE"
        level = "L1"

    report = {
        "protocol_v3_sha256": protocol_sha,
        "decision": decision,
        "credibility_level": level,
        "acceptance": acceptance,
        "NEAR_lobo": near_res,
        "FAR_lobo": far_res,
        "SLOPE_MATCHED_lobo": slope_res,
        "sealed_fresh": sealed_eval,
        "exploratory_spent_v2": spent_eval,
        "power_summary": power["summary"],
    }
    write_json(OUT / "phase4_eval.json", report)
    write_json(OUT / "phase9_decision.json", {"decision": decision, "credibility_level": level, "acceptance": acceptance})
    append_log(f"END lobo_eval decision={decision}")
    print(json.dumps({"decision": decision, "level": level, "acceptance": acceptance}, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
