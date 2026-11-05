"""Re-check protocol/corpus hashes and regenerate headline NEAR metrics."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import CORPUS, OUT, PROTOCOL_V1, PROTOCOL_V2, FEATURE_NAMES, sha256_file  # noqa: E402
import pickle
import numpy as np
from common import roc_auc, bootstrap_block, delta_auc_boot  # noqa: E402

EXPECTED_V1 = "BD2A86BC5A883123B476F9CFD759026836740C60E09FD6A9ACE3BD088213DDFE"
EXPECTED_V2 = "5F63E3625717B25750868985621C6C161BDC9B31C295B7585E47BCD77796FEF5"


def main() -> int:
    v1 = sha256_file(PROTOCOL_V1)
    v2 = sha256_file(PROTOCOL_V2)
    man = json.loads((CORPUS / "manifest.json").read_text(encoding="utf-8"))
    near_hash = sha256_file(CORPUS / "samples_near.jsonl")
    ok = v1 == EXPECTED_V1 and v2 == EXPECTED_V2 and near_hash == man["file_hashes"]["samples_near.jsonl"]
    # reload scores via frozen HGB
    rows = [json.loads(l) for l in (CORPUS / "samples_near.jsonl").open(encoding="utf-8")]
    test = [r for r in rows if r["split"] == "test"]
    train = [r for r in rows if r["split"] == "train"]
    Xte = np.asarray([[r[f"f_{n}"] for n in FEATURE_NAMES] for r in test], float)
    yte = np.asarray([r["y"] for r in test], int)
    blocks = [r["block"] for r in test]
    Xtr = np.asarray([[r[f"f_{n}"] for n in FEATURE_NAMES] for r in train], float)
    slope = Xte[:, FEATURE_NAMES.index("slope")]
    ref = np.sort(Xtr[:, FEATURE_NAMES.index("slope")])
    slope_s = np.searchsorted(ref, slope, side="right") / max(len(ref), 1)
    payload = pickle.load((CORPUS / "models" / "NEAR_hgb.pkl").open("rb"))
    raw = payload["model"].predict_proba(Xte)[:, 1]
    cal = payload.get("cal")
    if cal:
        from train_eval import apply_cal

        scores = apply_cal(cal, raw)
    else:
        scores = raw
    auc = roc_auc(yte, scores)
    sauc = roc_auc(yte, slope_s)
    report = {
        "protocol_v1_ok": v1 == EXPECTED_V1,
        "protocol_v2_ok": v2 == EXPECTED_V2,
        "samples_near_hash_ok": near_hash == man["file_hashes"]["samples_near.jsonl"],
        "regen_hgb_test_auc": auc,
        "regen_slope_test_auc": sauc,
        "expected_hgb_auc_approx": 0.8504232804232804,
        "match_within_1e-6": abs((auc or 0) - 0.8504232804232804) < 1e-6,
        "all_ok": ok and abs((auc or 0) - 0.8504232804232804) < 1e-6,
    }
    (OUT / "verify_repro.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))
    return 0 if report["all_ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
