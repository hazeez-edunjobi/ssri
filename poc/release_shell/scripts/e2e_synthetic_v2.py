"""End-to-end SYNTHETIC v2: upload → validate → 3-seed train → evaluate → assess.

Also demonstrates v1-shaped input rejected against a v2 checkpoint (named missing channels).
LOCAL ONLY — not real geology.
"""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs" / "e2e_synthetic_v2"
OUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = (
    Path(__file__).resolve().parents[1] / "templates" / "SYNTHETIC_stage25_v2_template.zip"
)

os.environ["SSRI_RELEASE_SHELL"] = "true"
os.environ["SSRI_ASSESS_SOFTMAX"] = "true"
os.environ["SSRI_RELEASE_SHELL_BUFFER_KM"] = "0"
os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "1"
os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "4"
os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "1"


def _ensure_template() -> None:
    if TEMPLATE.exists():
        return
    import runpy

    build_path = Path(__file__).resolve().parent / "build_synthetic_v2_template.py"
    sys.path.insert(0, str(REPO / "model" / "src"))
    runpy.run_path(str(build_path), run_name="__main__")
    if not TEMPLATE.exists():
        raise SystemExit(f"Failed to build template at {TEMPLATE}")


def main() -> int:
    model_root = REPO / "model"
    sys.path.insert(0, str(model_root / "src"))
    sys.path.insert(0, str(model_root))
    sys.path.insert(0, str(model_root / "tests"))

    _ensure_template()

    from ssri_model.api.app import create_app
    from api_helpers import build_api_config  # type: ignore

    log: dict = {"steps": {}, "pass": False}
    tmp = OUT / "work"
    tmp.mkdir(parents=True, exist_ok=True)
    client = TestClient(create_app(build_api_config(tmp)))

    create = client.post(
        "/api/v1/training/datasets",
        json={"name": "SYNTHETIC-v2-e2e", "notes": "SYNTHETIC schema v2"},
    )
    ds_id = create.json()["dataset"]["dataset_id"]
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds_id}/upload",
        files={
            "file": (
                "SYNTHETIC_stage25_v2_template.zip",
                TEMPLATE.read_bytes(),
                "application/zip",
            )
        },
    )
    val = client.post(f"/api/v1/release-shell/datasets/{ds_id}/validate")
    val_body = val.json()
    log["steps"]["upload_validate"] = {
        "upload_status": up.status_code,
        "validate_status": val.status_code,
        "overall": (val_body.get("validation") or {}).get("overall"),
        "can_train": (val_body.get("validation") or {}).get("can_train"),
        "channel_schema": (val_body.get("validation") or {}).get("channel_schema"),
        "pass": up.status_code == 200
        and (val_body.get("validation") or {}).get("can_train") is True,
    }

    start = client.post(
        "/api/v1/release-shell/jobs",
        json={
            "dataset_id": ds_id,
            "epochs": 1,
            "batch_size": 2,
            "seeds": [42, 43, 44],
            "device": "cpu",
            "learning_rate": 1e-3,
        },
    )
    start_body = start.json()
    job_id = start_body.get("job_id")
    run_id = start_body.get("run_id")
    final = None
    poll_log: list[dict] = []
    if job_id:
        for i in range(180):
            time.sleep(2)
            j = client.get(f"/api/v1/jobs/{job_id}")
            final = j.json()
            st = str(
                final.get("status")
                or (final.get("job") or {}).get("status")
                or ""
            ).lower()
            poll_log.append({"i": i, "status": st, "keys": list(final.keys())[:12]})
            if st in {"completed", "failed", "succeeded", "success"}:
                break

    job_ok = bool(
        final
        and str(final.get("status") or (final.get("job") or {}).get("status") or "")
        .lower()
        in {"completed", "succeeded", "success"}
    )
    log["steps"]["train"] = {
        "start_status": start.status_code,
        "start": start_body,
        "job_id": job_id,
        "run_id": run_id,
        "job_final": final,
        "poll_tail": poll_log[-5:],
        "pass": start.status_code in {200, 202} and job_ok,
    }

    # Locate checkpoint
    models = client.get("/api/v1/training/models").json()
    model_list = models.get("models") or models if isinstance(models, dict) else []
    if isinstance(model_list, dict):
        model_list = model_list.get("models") or []
    ckpt = None
    model_id = None
    for m in model_list:
        if m.get("dataset_id") == ds_id and m.get("checkpoint_path"):
            ckpt = m["checkpoint_path"]
            model_id = m.get("model_id")
            break

    eval_body = None
    if model_id:
        ev = client.get(f"/api/v1/release-shell/models/{model_id}/evaluation")
        eval_body = ev.json() if ev.status_code == 200 else {"status_code": ev.status_code, "text": ev.text[:800]}
        log["steps"]["evaluate"] = {
            "status_code": ev.status_code,
            "body": eval_body,
            "pass": ev.status_code == 200,
        }
    else:
        log["steps"]["evaluate"] = {"pass": False, "error": "no model_id"}

    assess_ok = False
    mismatch_ok = False
    if ckpt and Path(ckpt).is_file():
        feat_v2 = tmp / "features_v2.npy"
        np.save(feat_v2, np.zeros((16, 16, 16), dtype=np.float32))
        a = client.post(
            "/api/v1/assess",
            json={"checkpoint": str(ckpt), "features": str(feat_v2)},
        )
        a_body = a.json()
        assess_ok = (
            a.status_code == 200
            and a_body.get("channel_schema_version") == "v2"
            and isinstance(a_body.get("channel_names"), list)
            and len(a_body.get("channel_names") or []) == 16
        )
        log["steps"]["assess_v2"] = {
            "status_code": a.status_code,
            "channel_schema_version": a_body.get("channel_schema_version"),
            "channel_names": a_body.get("channel_names"),
            "notes_sample": (a_body.get("notes") or [])[:12],
            "body_keys": list(a_body.keys()),
            "pass": assess_ok,
            "checkpoint": ckpt,
        }

        feat_v1 = tmp / "features_v1.npy"
        np.save(feat_v1, np.zeros((13, 16, 16), dtype=np.float32))
        bad = client.post(
            "/api/v1/assess",
            json={"checkpoint": str(ckpt), "features": str(feat_v1)},
        )
        bad_body = bad.json() if bad.headers.get("content-type", "").startswith("application/json") else {"text": bad.text[:800]}
        msg = json.dumps(bad_body)
        mismatch_ok = bad.status_code in {400, 422} and all(
            name in msg
            for name in (
                "overburden_thickness",
                "lineament_density",
                "lineament_distance",
            )
        )
        log["steps"]["assess_v1_reject"] = {
            "status_code": bad.status_code,
            "body": bad_body,
            "pass": mismatch_ok,
        }
    else:
        log["steps"]["assess_v2"] = {"pass": False, "error": "no checkpoint", "job_final": final}
        log["steps"]["assess_v1_reject"] = {"pass": False, "error": "no checkpoint"}

    log["pass"] = all(
        log["steps"].get(k, {}).get("pass")
        for k in (
            "upload_validate",
            "train",
            "evaluate",
            "assess_v2",
            "assess_v1_reject",
        )
    )
    path = OUT / "e2e_log.json"
    path.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"pass": log["pass"], "log": str(path)}, indent=2))
    # Print job log + assess response for the operator transcript
    print("--- JOB FINAL ---")
    print(json.dumps(log["steps"].get("train", {}).get("job_final"), indent=2, default=str)[:4000])
    print("--- ASSESS V2 ---")
    print(json.dumps(log["steps"].get("assess_v2"), indent=2, default=str)[:4000])
    print("--- ASSESS V1 REJECT ---")
    print(json.dumps(log["steps"].get("assess_v1_reject"), indent=2, default=str)[:4000])
    return 0 if log["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
