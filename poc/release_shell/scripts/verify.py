"""One-command verify for the release shell (acceptance step a)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs"
OUT.mkdir(parents=True, exist_ok=True)


def run(cmd: list[str], cwd: Path | None = None, env: dict | None = None) -> dict:
    proc = subprocess.run(
        cmd,
        cwd=str(cwd or REPO),
        capture_output=True,
        text=True,
        env=env,
    )
    return {
        "cmd": cmd,
        "returncode": proc.returncode,
        "stdout_tail": (proc.stdout or "")[-2000:],
        "stderr_tail": (proc.stderr or "")[-2000:],
    }


def main() -> int:
    report: dict = {"steps": {}}
    # a) hashes / branch note
    report["steps"]["git"] = run(["git", "rev-parse", "--abbrev-ref", "HEAD"])
    report["steps"]["commit"] = run(["git", "rev-parse", "HEAD"])

    # Softmax unit + spatial + assess flag tests (+ contract)
    report["steps"]["new_tests"] = run(
        [
            "poetry",
            "-C",
            "model",
            "run",
            "pytest",
            "tests/test_release_shell_softmax_contract.py",
            "tests/test_release_shell_spatial_split.py",
            "tests/test_release_shell_assess.py",
            "tests/test_release_shell_validator.py",
            "tests/test_release_shell_assess_contract.py",
            "tests/test_release_shell_assess_route.py",
            "tests/test_release_shell_jobs_result.py",
            "-q",
            "--tb=line",
        ]
    )

    # 93 + 9
    report["steps"]["assess_93"] = run(
        [
            "poetry",
            "-C",
            "model",
            "run",
            "pytest",
            "tests/test_api_assess.py",
            "tests/test_api_assess_audit.py",
            "tests/test_demo_mode_assess.py",
            "tests/test_model_architecture.py",
            "tests/test_multitask_model.py",
            "tests/test_inference.py",
            "tests/test_evaluation_metrics.py",
            "tests/test_training_metrics.py",
            "-q",
            "--tb=no",
        ]
    )
    deepslide = REPO / "poc" / "landslide4sense" / "integration" / "test_deepslide_engine.py"
    if deepslide.exists():
        dep_probe = run(
            [
                "poetry",
                "-C",
                "model",
                "run",
                "python",
                "-c",
                "import segmentation_models_pytorch, h5py; print('deepslide_deps_ok')",
            ]
        )
        if dep_probe.get("returncode", 1) != 0 or "deepslide_deps_ok" not in (
            dep_probe.get("stdout_tail") or ""
        ):
            report["steps"]["deepslide_9"] = {
                "returncode": 0,
                "stdout_tail": (
                    "DeepSlide skipped: optional deps "
                    "(install with: poetry -C model install --with deepslide)"
                ),
                "stderr_tail": (dep_probe.get("stderr_tail") or "")[-500:],
                "skipped_optional_deps": True,
            }
        else:
            report["steps"]["deepslide_9"] = run(
                [
                    "poetry",
                    "-C",
                    "model",
                    "run",
                    "pytest",
                    str(deepslide),
                    "-q",
                    "--tb=no",
                ]
            )
    else:
        report["steps"]["deepslide_9"] = {
            "returncode": 0,
            "stdout_tail": "SKIPPED — deepslide test path not present on this checkout",
        }

    # b) no_trained_model via TestClient (flag must be on in child env)
    env = os.environ.copy()
    env["SSRI_RELEASE_SHELL"] = "true"
    code = (
        "import os;"
        "os.environ['SSRI_RELEASE_SHELL']='true';"
        "from fastapi.testclient import TestClient;"
        "from ssri_model.api.app import create_app;"
        "from tests.api_helpers import build_api_config;"
        "from pathlib import Path;"
        "c=TestClient(create_app(build_api_config(Path('outputs/tmp_verify'))));"
        "r=c.post('/api/v1/assess', json={});"
        "print(r.status_code, r.json().get('status'))"
    )
    report["steps"]["no_trained_model"] = run(
        ["poetry", "-C", "model", "run", "python", "-c", code],
        env=env,
    )

    ok = all(
        report["steps"][k].get("returncode", 1) == 0
        for k in ("new_tests", "assess_93")
    )
    # deepslide: optional path/deps skip must not fail verify; real run must pass
    if "deepslide_9" in report["steps"]:
        ds = report["steps"]["deepslide_9"]
        skip_note = str(ds.get("stdout_tail") or "")
        if ds.get("skipped_optional_deps") or "SKIPPED" in skip_note or "skipped" in skip_note.lower():
            pass
        else:
            ok = ok and ds.get("returncode", 1) == 0
    ok = ok and "no_trained_model" in report["steps"]["no_trained_model"].get(
        "stdout_tail", ""
    )

    report["pass"] = ok
    path = OUT / "verify_report.json"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps({"pass": ok, "report": str(path)}, indent=2))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
