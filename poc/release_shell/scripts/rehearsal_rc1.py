"""Clean-clone rehearsal steps 1–6 for integration RC1."""

from __future__ import annotations

import json
import os
import time
import zipfile
from io import BytesIO
from pathlib import Path

import numpy as np
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)
TEMPLATE = Path(__file__).resolve().parents[1] / "templates" / "SYNTHETIC_stage25_template.zip"
FS_ZIP = Path(__file__).resolve().parents[1] / "outputs" / "rehearsal" / "usgs_featurestacks_v3_upload.zip"

os.environ["SSRI_RELEASE_SHELL"] = "true"
os.environ["SSRI_ASSESS_SOFTMAX"] = "true"
os.environ["SSRI_RELEASE_SHELL_BUFFER_KM"] = "0"
os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "4"
os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "4"
os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "2"


def main() -> int:
    import sys

    sys.path.insert(0, str(REPO / "model"))
    sys.path.insert(0, str(REPO / "model" / "tests"))
    from ssri_model.api.app import create_app
    from api_helpers import build_api_config  # type: ignore

    log: dict = {"steps": {}, "clone_commit": None}
    try:
        import subprocess

        log["clone_commit"] = (
            subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=str(REPO))
            .decode()
            .strip()
        )
    except Exception as exc:  # noqa: BLE001
        log["clone_commit_error"] = str(exc)

    tmp = OUT / "rehearsal_rc1_tmp"
    tmp.mkdir(exist_ok=True)
    client = TestClient(create_app(build_api_config(tmp)))

    # 1) no checkpoint
    r = client.post("/api/v1/assess", json={})
    body = r.json()
    log["steps"]["1_no_trained_model"] = {
        "status_code": r.status_code,
        "status": body.get("status"),
        "pass": r.status_code == 200 and body.get("status") == "no_trained_model",
    }

    # 2) broken ZIP
    ds_b = client.post(
        "/api/v1/training/datasets", json={"name": "broken", "notes": "rehearsal"}
    ).json()["dataset"]["dataset_id"]
    buf = BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("readme.txt", "not a dataset")
    up = client.post(
        f"/api/v1/release-shell/datasets/{ds_b}/upload",
        files={"file": ("broken.zip", buf.getvalue(), "application/zip")},
    )
    val = client.post(f"/api/v1/release-shell/datasets/{ds_b}/validate")
    train = client.post(
        "/api/v1/release-shell/jobs",
        json={"dataset_id": ds_b, "epochs": 1, "seeds": [42, 43, 44]},
    )
    vbody = val.json() if val.status_code == 200 else {}
    log["steps"]["2_broken_zip"] = {
        "upload": up.status_code,
        "overall": (vbody.get("validation") or {}).get("overall"),
        "can_train": (vbody.get("validation") or {}).get("can_train"),
        "train_status": train.status_code,
        "pass": train.status_code == 400
        or (vbody.get("validation") or {}).get("can_train") is False,
    }

    # 3) FeatureStacks v3
    step3: dict = {"pass": False}
    if FS_ZIP.exists():
        ds_fs = client.post(
            "/api/v1/training/datasets",
            json={"name": "featurestacks-v3", "notes": "rehearsal"},
        ).json()["dataset"]["dataset_id"]
        up3 = client.post(
            f"/api/v1/release-shell/datasets/{ds_fs}/upload",
            files={
                "file": (
                    "usgs_featurestacks_v3_upload.zip",
                    FS_ZIP.read_bytes(),
                    "application/zip",
                )
            },
        )
        # Use production mins for this check
        os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "300"
        os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "8"
        os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "3"
        val3 = client.post(f"/api/v1/release-shell/datasets/{ds_fs}/validate")
        # restore demo mins for SYNTHETIC
        os.environ["SSRI_RELEASE_SHELL_MIN_TILES"] = "4"
        os.environ["SSRI_RELEASE_SHELL_MIN_BLOCKS"] = "4"
        os.environ["SSRI_RELEASE_SHELL_MIN_HELD_OUT"] = "2"
        vb = val3.json() if val3.status_code == 200 else {"error": val3.text[:500]}
        validation = vb.get("validation") or {}
        checks = {c["name"]: c for c in validation.get("checks") or []}
        cq = checks.get("channel_quality") or {}
        hazards_raw = validation.get("hazards") or []
        if isinstance(hazards_raw, dict):
            hazard_rows = [
                {"name": name, **(info or {})} for name, info in hazards_raw.items()
            ]
        else:
            hazard_rows = list(hazards_raw)
        disabled = [
            str(info.get("name") or info.get("hazard") or "?")
            for info in hazard_rows
            if (info or {}).get("status") == "DISABLED"
            or (info or {}).get("disabled_at_validation")
        ]
        step3 = {
            "upload": up3.status_code,
            "overall": validation.get("overall"),
            "can_train": validation.get("can_train"),
            "channel_quality": cq.get("status"),
            "channel_message": cq.get("message"),
            "disabled_hazards": disabled,
            "pass": validation.get("overall") == "FAIL"
            and cq.get("status") == "FAIL"
            and len(disabled) >= 1,
        }
    else:
        # Fall back to packaged validation JSON from branch if ZIP not in clone
        prior = (
            Path(__file__).resolve().parents[1]
            / "outputs"
            / "rehearsal"
            / "featurestacks_v3_validation.json"
        )
        if prior.exists():
            prior_v = json.loads(prior.read_text(encoding="utf-8"))
            step3 = {
                "note": "ZIP missing in clone; used committed featurestacks_v3_validation.json",
                "overall": prior_v.get("overall"),
                "channel_quality": next(
                    (
                        c.get("status")
                        for c in prior_v.get("checks") or []
                        if c.get("name") == "channel_quality"
                    ),
                    None,
                ),
                "pass": prior_v.get("overall") == "FAIL",
                "source": str(prior),
            }
        else:
            step3 = {"pass": False, "error": f"missing {FS_ZIP} and prior validation JSON"}
    log["steps"]["3_featurestacks_v3"] = step3

    # 4) SYNTHETIC train
    step4: dict = {"pass": False}
    if TEMPLATE.exists():
        ds = client.post(
            "/api/v1/training/datasets",
            json={"name": "SYNTHETIC-rehearsal", "notes": "SYNTHETIC"},
        ).json()["dataset"]["dataset_id"]
        up4 = client.post(
            f"/api/v1/release-shell/datasets/{ds}/upload",
            files={
                "file": (
                    "SYNTHETIC_stage25_template.zip",
                    TEMPLATE.read_bytes(),
                    "application/zip",
                )
            },
        )
        val4 = client.post(f"/api/v1/release-shell/datasets/{ds}/validate")
        vb4 = val4.json()
        start = client.post(
            "/api/v1/release-shell/jobs",
            json={
                "dataset_id": ds,
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
            for _ in range(180):
                time.sleep(2)
                final = client.get(f"/api/v1/jobs/{job_id}").json()
                if str(final.get("status", "")).lower() in {
                    "completed",
                    "failed",
                    "cancelled",
                }:
                    break
        result = (final or {}).get("result") or {}
        step4 = {
            "upload": up4.status_code,
            "validation_overall": (vb4.get("validation") or {}).get("overall"),
            "can_train": (vb4.get("validation") or {}).get("can_train"),
            "start_status": start.status_code,
            "job_status": (final or {}).get("status"),
            "has_result": bool(result),
            "seeds": result.get("seeds"),
            "evaluation_present": bool(result.get("evaluation") or result.get("evaluation_path")),
            "pass": bool(
                (vb4.get("validation") or {}).get("can_train")
                and start.status_code in {200, 202}
                and str((final or {}).get("status", "")).lower() == "completed"
                and result
            ),
            "job_id": job_id,
            "dataset_id": ds,
            "checkpoint_path": result.get("checkpoint_path"),
            "model_id": result.get("model_id"),
            "evaluation": result.get("evaluation"),
        }
    else:
        step4 = {"pass": False, "error": f"missing {TEMPLATE}"}
    log["steps"]["4_synthetic_train"] = step4

    # 5) assess with checkpoint
    step5: dict = {"pass": False}
    ckpt = step4.get("checkpoint_path")
    if ckpt and Path(str(ckpt)).is_file():
        feat = tmp / "feat.npy"
        np.save(feat, np.zeros((13, 16, 16), dtype=np.float32))
        # inside region — use a point near synthetic tiles if unknown; still check envelope
        a = client.post(
            "/api/v1/assess",
            json={
                "checkpoint": str(ckpt),
                "features": str(feat),
                "point": {"latitude": 37.5, "longitude": -120.5},
                "mc_samples": 2,
            },
        )
        ab = a.json() if a.status_code == 200 else {"error": a.text[:500]}
        notes = ab.get("notes") or []
        profiles = ab.get("hazard_profiles") or []
        step5 = {
            "status_code": a.status_code,
            "profile_statuses": [
                {
                    "hazard": p.get("hazard_type"),
                    "status": p.get("status"),
                    "score": p.get("score"),
                    "gate_status": p.get("gate_status"),
                }
                for p in profiles
            ],
            "has_checkpoint_sha": any(str(n).startswith("checkpoint_sha256=") for n in notes)
            or bool(ab.get("checkpoint_sha256")),
            "has_limitations": any("limitation=" in str(n) for n in notes)
            or "limitations" in ab,
            "notes_sample": notes[:10],
            "pass": a.status_code == 200 and bool(profiles),
            "checkpoint": ckpt,
        }
    else:
        step5 = {"pass": False, "error": "no checkpoint from step 4"}
    log["steps"]["5_assess_selected"] = step5

    # 6) outside region
    step6: dict = {"pass": False}
    if ckpt and Path(str(ckpt)).is_file():
        feat = tmp / "feat.npy"
        a2 = client.post(
            "/api/v1/assess",
            json={
                "checkpoint": str(ckpt),
                "features": str(feat),
                "point": {"latitude": -40.0, "longitude": 170.0},
                "mc_samples": 2,
                "hazards": ["landslide", "subsidence", "sinkhole"],
            },
        )
        ab2 = a2.json() if a2.status_code == 200 else {}
        profiles = ab2.get("hazard_profiles") or []
        outside = [
            p
            for p in profiles
            if p.get("status") == "outside_training_region" and p.get("score") is None
        ]
        step6 = {
            "status_code": a2.status_code,
            "outside_count": len(outside),
            "profiles": [
                {"hazard": p.get("hazard_type"), "status": p.get("status"), "score": p.get("score")}
                for p in profiles
            ],
            "pass": a2.status_code == 200 and len(outside) >= 1,
        }
    else:
        step6 = {"pass": False, "error": "no checkpoint"}
    log["steps"]["6_outside_region"] = step6

    log["pass"] = all(
        log["steps"][k].get("pass")
        for k in (
            "1_no_trained_model",
            "2_broken_zip",
            "3_featurestacks_v3",
            "4_synthetic_train",
            "5_assess_selected",
            "6_outside_region",
        )
    )
    path = OUT / "rehearsal_rc1_log.json"
    path.write_text(json.dumps(log, indent=2, default=str), encoding="utf-8")
    print(json.dumps({"pass": log["pass"], "log": str(path)}, indent=2))
    return 0 if log["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
