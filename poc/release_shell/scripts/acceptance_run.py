"""Acceptance test log for release shell (steps b–e)."""

from __future__ import annotations

import json
import os
import time
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "SYNTHETIC_stage25_template.zip"

os.environ["SSRI_RELEASE_SHELL"] = "true"
os.environ["SSRI_ASSESS_SOFTMAX"] = "true"
os.environ["SSRI_RELEASE_SHELL_BUFFER_KM"] = "0"
os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "4"
os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "4"
os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "2"


def main() -> int:
    import sys

    model_root = REPO / "model"
    sys.path.insert(0, str(model_root))
    sys.path.insert(0, str(model_root / "tests"))
    from ssri_model.api.app import create_app
    from api_helpers import build_api_config  # type: ignore

    log: dict = {"steps": {}}
    tmp = OUT / "acceptance_tmp"
    tmp.mkdir(exist_ok=True)
    client = TestClient(create_app(build_api_config(tmp)))

    # b) no_trained_model
    r = client.post("/api/v1/assess", json={})
    log["steps"]["b_no_trained_model"] = {
        "status_code": r.status_code,
        "body": r.json(),
        "pass": r.status_code == 200 and r.json().get("status") == "no_trained_model",
    }

    # c) broken ZIP
    create = client.post(
        "/api/v1/training/datasets",
        json={"name": "broken-demo", "notes": "acceptance"},
    )
    ds_broken = create.json()["dataset"]["dataset_id"]
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "not a dataset")
    buf.seek(0)
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds_broken}/upload",
        files={"file": ("broken.zip", buf.getvalue(), "application/zip")},
    )
    # ingest may error or validate FAIL
    val = client.post(f"/api/v1/release-shell/datasets/{ds_broken}/validate")
    train_refuse = client.post(
        "/api/v1/release-shell/jobs",
        json={"dataset_id": ds_broken, "epochs": 1, "seeds": [42, 43, 44]},
    )
    log["steps"]["c_broken_zip"] = {
        "upload_status": up.status_code,
        "upload_body": up.json() if up.headers.get("content-type", "").startswith("application/json") else up.text[:500],
        "validate": val.json() if val.status_code == 200 else {"status_code": val.status_code, "body": val.text[:800]},
        "train_refuse_status": train_refuse.status_code,
        "train_refuse": train_refuse.json(),
        "pass": train_refuse.status_code == 400
        or (
            val.status_code == 200
            and val.json().get("validation", {}).get("can_train") is False
        ),
    }

    # d) SYNTHETIC template
    if not TEMPLATE.exists():
        log["steps"]["d_synthetic"] = {"pass": False, "error": f"missing {TEMPLATE}"}
    else:
        create2 = client.post(
            "/api/v1/training/datasets",
            json={"name": "SYNTHETIC-demo", "notes": "SYNTHETIC"},
        )
        ds_id = create2.json()["dataset"]["dataset_id"]
        up2 = client.post(
            f"/api/v1/release-shell/datasets/{ds_id}/upload",
            files={
                "file": (
                    "SYNTHETIC_stage25_template.zip",
                    TEMPLATE.read_bytes(),
                    "application/zip",
                )
            },
        )
        val2 = client.post(f"/api/v1/release-shell/datasets/{ds_id}/validate")
        val_body = val2.json()
        start = client.post(
            "/api/v1/release-shell/jobs",
            json={
                "dataset_id": ds_id,
                "epochs": 2,
                "batch_size": 2,
                "seeds": [42, 43, 44],
                "device": "cpu",
            },
        )
        start_body = start.json()
        job_id = start_body.get("job_id")
        final = None
        if job_id:
            for _ in range(120):
                time.sleep(2)
                j = client.get(f"/api/v1/jobs/{job_id}")
                final = j.json()
                st = str(final.get("status") or final.get("job", {}).get("status") or "")
                if st.lower() in {"completed", "failed", "succeeded", "success"}:
                    break
        job_ok = bool(
            final
            and str(final.get("status", "")).lower() in {"completed", "succeeded", "success"}
        )
        log["steps"]["d_synthetic"] = {
            "upload": up2.status_code,
            "validation_overall": val_body.get("validation", {}).get("overall"),
            "can_train": val_body.get("validation", {}).get("can_train"),
            "start_status": start.status_code,
            "start": start_body,
            "job_final": final,
            "pass": bool(
                up2.status_code == 200
                and val_body.get("validation", {}).get("can_train")
                and start.status_code in {200, 202}
                and job_ok
            ),
        }

        # e) assess with checkpoint — jobs API may omit result body; use models list
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
        step_e = {"pass": False, "models_seen": len(model_list)}
        if ckpt and Path(ckpt).is_file():
            import numpy as np

            feat = tmp / "SYNTHETIC_features.npy"
            np.save(feat, np.zeros((13, 16, 16), dtype=np.float32))
            a = client.post(
                "/api/v1/assess",
                json={"checkpoint": str(ckpt), "features": str(feat)},
            )
            step_e.update(
                {
                    "status_code": a.status_code,
                    "body_keys": list(a.json().keys()) if a.status_code == 200 else a.text[:500],
                    "notes_sample": (a.json().get("notes") or [])[:8]
                    if a.status_code == 200
                    else None,
                    "pass": a.status_code == 200,
                    "checkpoint": ckpt,
                    "model_id": model_id,
                }
            )
            if model_id:
                ev = client.get(f"/api/v1/release-shell/models/{model_id}/evaluation")
                step_e["evaluation_status"] = ev.status_code
                step_e["evaluation"] = (
                    ev.json() if ev.status_code == 200 else ev.text[:800]
                )
                if ev.status_code == 200:
                    step_e["pass"] = step_e["pass"] and True
        else:
            step_e["error"] = "No checkpoint found in /training/models for dataset"
            step_e["job_final"] = final
        log["steps"]["e_assess"] = step_e

    log["pass"] = all(
        log["steps"].get(k, {}).get("pass")
        for k in ("b_no_trained_model", "c_broken_zip", "d_synthetic", "e_assess")
    )
    path = OUT / "acceptance_log.json"
    path.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"pass": log["pass"], "log": str(path)}, indent=2))
    return 0 if log["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
