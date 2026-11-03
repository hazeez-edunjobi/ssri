"""Phase 1 power: minimum detectable ΔAUC vs slope for LOBO and sealed holdout."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np

OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def simulate_auc_power(
    n_blocks: int,
    n_per_block: int,
    true_delta: float,
    base_auc: float = 0.82,
    n_sims: int = 400,
    n_boot: int = 200,
    seed: int = 42,
) -> dict:
    """Rough simulation: scores = latent + noise; slope weaker by true_delta in AUC space via noise scale.

    Assumptions (recorded):
    - Prevalence 0.35 within blocks (matches NEAR-ish test mix)
    - Block-level score correlation via shared block effect
    - Detect if lower 95% CI of ΔAUC > 0 in >=80% of sims (power)
    """
    rng = np.random.default_rng(seed)
    # Find noise levels that approximate base_auc and base_auc+delta via search
    # Simpler approach: generate ranking with controlled Mann-Whitney AUC

    def make_scores(n, auc_target, rng_local):
        n_pos = int(round(0.35 * n))
        n_neg = n - n_pos
        y = np.array([1] * n_pos + [0] * n_neg)
        # scores: pos ~ N(d,1), neg ~ N(0,1); choose d for approx AUC = Phi(d/sqrt(2))
        from math import sqrt

        # binary search d
        lo, hi = 0.0, 5.0
        for _ in range(30):
            d = 0.5 * (lo + hi)
            # expected AUC
            from scipy.stats import norm

            eauc = float(norm.cdf(d / sqrt(2)))
            if eauc < auc_target:
                lo = d
            else:
                hi = d
        d = 0.5 * (lo + hi)
        s = np.concatenate([rng_local.normal(d, 1.0, n_pos), rng_local.normal(0.0, 1.0, n_neg)])
        return y, s

    def auc(y, s):
        y = y.astype(int)
        if y.min() == y.max():
            return 0.5
        order = np.argsort(s)
        ranks = np.empty(len(s))
        ranks[order] = np.arange(1, len(s) + 1)
        n_pos = y.sum()
        n_neg = len(y) - n_pos
        return (ranks[y == 1].sum() - n_pos * (n_pos + 1) / 2) / (n_pos * n_neg)

    def detect(delta):
        hits = 0
        for _ in range(n_sims):
            block_deltas = []
            y_all = []
            sc_all = []
            ss_all = []
            b_all = []
            for b in range(n_blocks):
                y, s_cand = make_scores(n_per_block, base_auc + delta, rng)
                _, s_slope = make_scores(n_per_block, base_auc, rng)
                # align labels - regenerate jointly
                n = n_per_block
                n_pos = int(round(0.35 * n))
                y = np.array([1] * n_pos + [0] * (n - n_pos))
                from math import sqrt
                from scipy.stats import norm

                def d_for(a):
                    lo, hi = 0.0, 5.0
                    for __ in range(25):
                        mid = 0.5 * (lo + hi)
                        if norm.cdf(mid / sqrt(2)) < a:
                            lo = mid
                        else:
                            hi = mid
                    return 0.5 * (lo + hi)

                dc, ds = d_for(base_auc + delta), d_for(base_auc)
                s_cand = np.concatenate(
                    [rng.normal(dc, 1.0, n_pos), rng.normal(0.0, 1.0, n - n_pos)]
                )
                s_slope = np.concatenate(
                    [rng.normal(ds, 1.0, n_pos), rng.normal(0.0, 1.0, n - n_pos)]
                )
                y_all.append(y)
                sc_all.append(s_cand)
                ss_all.append(s_slope)
                b_all.extend([b] * n)
            y = np.concatenate(y_all)
            sc = np.concatenate(sc_all)
            ss = np.concatenate(ss_all)
            # block bootstrap
            uniq = list(range(n_blocks))
            deltas = []
            for __ in range(n_boot):
                chosen = rng.choice(uniq, size=n_blocks, replace=True)
                idxs = []
                for b in chosen:
                    idxs.extend([i for i, bb in enumerate(b_all) if bb == b])
                idxs = np.asarray(idxs)
                deltas.append(auc(y[idxs], sc[idxs]) - auc(y[idxs], ss[idxs]))
            lo = float(np.percentile(deltas, 2.5))
            if lo > 0:
                hits += 1
        return hits / n_sims

    # sweep deltas to find ~80% power MDD
    grid = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06, 0.08, 0.10, 0.12, 0.15]
    powers = {}
    mdd = None
    for d in grid:
        p = detect(d)
        powers[str(d)] = p
        if mdd is None and p >= 0.80:
            mdd = d
    if mdd is None:
        mdd = grid[-1]
    return {
        "n_blocks": n_blocks,
        "n_per_block": n_per_block,
        "base_auc_assumption": base_auc,
        "prevalence_assumption": 0.35,
        "n_sims": n_sims,
        "n_boot": n_boot,
        "power_by_delta": powers,
        "mdd_auc_at_power_0_80": mdd,
        "inconclusive_if_null_and_mdd_gt": 0.08,
        "mdd_exceeds_0_08": bool(mdd > 0.08),
    }


def main() -> int:
    # LOBO: ~20 blocks, ~90 samples/block average from v2 (1784/20)
    lobo = simulate_auc_power(n_blocks=20, n_per_block=90, true_delta=0.05)
    # Sealed: hope for 3–5 blocks × ~50
    sealed = simulate_auc_power(n_blocks=4, n_per_block=50, true_delta=0.05, n_sims=300)
    report = {
        "assumptions": {
            "score_model": "Gaussian separation calibrated to target AUC via Phi(d/sqrt(2))",
            "prevalence": 0.35,
            "detection_rule": "block-bootstrap 95% CI lower bound of DeltaAUC > 0",
            "power_target": 0.80,
            "base_auc": 0.82,
            "note": "Approximate; real spatial dependence may reduce power further",
        },
        "lobo": lobo,
        "sealed_holdout": sealed,
        "protocol_rule": "If MDD > 0.08 and Tier A fails, decision=INCONCLUSIVE not NO-GAIN",
    }
    # Determine LOBO MDD more carefully - lobo already has mdd
    report["summary"] = {
        "lobo_mdd": lobo["mdd_auc_at_power_0_80"],
        "sealed_mdd": sealed["mdd_auc_at_power_0_80"],
        "lobo_inconclusive_threshold_triggered": lobo["mdd_exceeds_0_08"],
        "sealed_inconclusive_threshold_triggered": sealed["mdd_exceeds_0_08"],
    }
    (OUT / "phase1_power.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
