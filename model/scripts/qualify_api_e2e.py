"""API-level end-to-end qualification against a running SSRI stack.

Does not launch a browser. Verifies health, async job, assess, and geojson rejection.
"""

from __future__ import annotations

import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


BASE = "http://127.0.0.1:8000"


def http_json(method: str, path: str, body: dict | None = None) -> tuple[int, dict | list | str]:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}{path}",
        data=data,
        method=method,
        headers={"Content-Type": "application/json"} if body is not None else {},
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            raw = resp.read().decode("utf-8")
            return int(resp.status), json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8")
        try:
            parsed: dict | list | str = json.loads(raw)
        except Exception:
            parsed = raw
        return int(exc.code), parsed


def main() -> int:
    results: list[str] = []
    code, ready = http_json("GET", "/api/v1/ready")
    results.append(f"ready={code}:{ready.get('status') if isinstance(ready, dict) else ready}")

    # Prepare fixtures inside API container when possible.
    prep = subprocess.run(
        [
            "docker",
            "compose",
            "-f",
            "infra/docker-compose.yml",
            "exec",
            "-T",
            "api",
            "python",
            "/tmp/docker_e2e_prepare_job.py",
        ],
        cwd=str(Path(__file__).resolve().parents[2]),
        capture_output=True,
        text=True,
    )
    if prep.returncode != 0:
        # Copy script then retry.
        root = Path(__file__).resolve().parents[2]
        subprocess.run(
            [
                "docker",
                "cp",
                str(root / "model/scripts/docker_e2e_prepare_job.py"),
                "ssri-api:/tmp/docker_e2e_prepare_job.py",
            ],
            check=False,
        )
        prep = subprocess.run(
            [
                "docker",
                "compose",
                "-f",
                "infra/docker-compose.yml",
                "exec",
                "-T",
                "api",
                "python",
                "/tmp/docker_e2e_prepare_job.py",
            ],
            cwd=str(root),
            capture_output=True,
            text=True,
        )
    if prep.returncode != 0:
        print("E2E_API=FAIL fixture_prep")
        print(prep.stderr[-500:])
        return 1
    payload = json.loads(prep.stdout.strip().splitlines()[-1])
    code, submitted = http_json("POST", "/api/v1/inference/async", payload)
    results.append(f"async_submit={code}")
    if code != 202 or not isinstance(submitted, dict):
        print("E2E_API=FAIL async_submit")
        print(results)
        return 1
    job_id = submitted["job_id"]
    final = None
    for _ in range(40):
        code, final = http_json("GET", f"/api/v1/jobs/{job_id}")
        if isinstance(final, dict) and final.get("status") in {"completed", "failed", "cancelled"}:
            break
        time.sleep(2)
    results.append(f"async_final={final.get('status') if isinstance(final, dict) else final}")

    assess_body = {
        "request_id": "qualify-assess-1",
        "checkpoint": payload["checkpoint"],
        "features": payload["features"],
        "hazards": ["subsidence"],
        "mc_samples": 8,
        "produce_geotiff": True,
    }
    code, assess = http_json("POST", "/api/v1/assess", assess_body)
    results.append(f"assess={code}")
    if isinstance(assess, dict):
        results.append(f"assess_id={assess.get('assessment_id')}")
        results.append(f"spatial={bool(assess.get('spatial_output_url'))}")

    # Invalid polygon should be rejected by assess live path or geojson util via API when live disabled.
    bad = {
        "request_id": "qualify-bad-poly",
        "checkpoint": payload["checkpoint"],
        "polygon_geojson": {"type": "Point", "coordinates": [3.0, 6.0]},
        "hazards": ["subsidence"],
    }
    code, _ = http_json("POST", "/api/v1/assess", bad)
    results.append(f"bad_polygon={code}")

    ok = (
        "async_final=completed" in results
        and any(r.startswith("assess=200") for r in results)
        and any(r.startswith("bad_polygon=") and r.split("=")[1] in {"400", "422"} for r in results)
    )
    print("E2E_API=" + ("OK" if ok else "FAIL"))
    for line in results:
        print(line)
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
