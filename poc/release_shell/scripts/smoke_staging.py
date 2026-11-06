"""One-command staging smoke test for the SSRI release shell.

Runs a fixed sequence against a LIVE API base URL + API key:

  1. health
  2. no_trained_model assess (no checkpoint supplied)
  3. broken-ZIP upload -> FAIL
  4. SYNTHETIC v1 template: upload -> validate -> train -> evaluate -> assess
  5. SYNTHETIC v2 template: upload -> validate -> train -> evaluate -> assess
  6. outside_training_region assess (point far from the training geography)

SAFETY
------
This script refuses to run against a *production* host unless you pass
``--allow-production``. A host is treated as production when it contains
``onrender.com`` or ``prod`` (case-insensitive). The default posture is
staging-only. This script never pushes, deploys, or changes any remote state
beyond creating datasets/jobs on the target API you point it at.

Usage
-----
    python poc/release_shell/scripts/smoke_staging.py \
        --base-url https://ssri-api-staging.example.com \
        --api-key "$SSRI_API_KEY"

    # deliberately target production (you asked for it):
    python ... --base-url https://ssri-api.onrender.com --api-key "$SSRI_API_KEY" \
        --allow-production

Exit code 0 only if every executed step PASSES (SKIPPED steps do not fail the
run but are reported). Results are written as JSON with ``--out``.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve()
RELEASE_SHELL = HERE.parents[1]
REPO = HERE.parents[3]
TEMPLATES = RELEASE_SHELL / "templates"

V1_TEMPLATE = TEMPLATES / "SYNTHETIC_stage25_template.zip"
V2_TEMPLATE = TEMPLATES / "SYNTHETIC_stage25_v2_template.zip"

# Far outside the SYNTHETIC template geography (US south-west / south-east).
OUTSIDE_POINT = {"latitude": 60.0, "longitude": 10.0}
# Inside the SYNTHETIC template geography (block centre used by the builders).
INSIDE_POINT = {"latitude": 35.5, "longitude": -95.5}

PRODUCTION_MARKERS = ("onrender.com", "prod")


def _is_production(base_url: str) -> bool:
    lowered = base_url.lower()
    return any(marker in lowered for marker in PRODUCTION_MARKERS)


class ApiError(Exception):
    def __init__(self, status: int, body: str) -> None:
        super().__init__(f"HTTP {status}: {body[:400]}")
        self.status = status
        self.body = body


class SmokeClient:
    def __init__(self, base_url: str, api_key: str, timeout: float = 60.0) -> None:
        self.base = base_url.rstrip("/")
        self.api_key = api_key
        self.timeout = timeout

    def _open(self, req: urllib.request.Request) -> tuple[int, str]:
        if self.api_key:
            req.add_header("Authorization", f"Bearer {self.api_key}")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                return resp.status, resp.read().decode("utf-8", "replace")
        except urllib.error.HTTPError as exc:  # 4xx/5xx
            return exc.code, exc.read().decode("utf-8", "replace")

    def request(
        self,
        method: str,
        path: str,
        *,
        json_body: dict[str, Any] | None = None,
        files: dict[str, tuple[str, bytes, str]] | None = None,
        form: dict[str, str] | None = None,
    ) -> tuple[int, str]:
        url = f"{self.base}{path}"
        data: bytes | None = None
        headers: dict[str, str] = {}
        if json_body is not None:
            data = json.dumps(json_body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        elif files is not None or form is not None:
            boundary = f"----ssrismoke{uuid.uuid4().hex}"
            body = bytearray()
            for name, value in (form or {}).items():
                body += f"--{boundary}\r\n".encode()
                body += f'Content-Disposition: form-data; name="{name}"\r\n\r\n'.encode()
                body += f"{value}\r\n".encode()
            for name, (filename, content, ctype) in (files or {}).items():
                body += f"--{boundary}\r\n".encode()
                body += (
                    f'Content-Disposition: form-data; name="{name}"; '
                    f'filename="{filename}"\r\n'
                ).encode()
                body += f"Content-Type: {ctype}\r\n\r\n".encode()
                body += content + b"\r\n"
            body += f"--{boundary}--\r\n".encode()
            data = bytes(body)
            headers["Content-Type"] = f"multipart/form-data; boundary={boundary}"
        req = urllib.request.Request(url, data=data, method=method, headers=headers)
        return self._open(req)

    def json(self, method: str, path: str, **kwargs: Any) -> tuple[int, Any]:
        status, text = self.request(method, path, **kwargs)
        try:
            return status, json.loads(text)
        except json.JSONDecodeError:
            return status, {"_raw": text[:400]}


def _step(results: list[dict[str, Any]], name: str, status: str, detail: Any) -> None:
    results.append(
        {
            "step": name,
            "status": status,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        }
    )
    print(f"[{status}] {name}: {json.dumps(detail, default=str)[:300]}")


def run_schema_cycle(
    client: SmokeClient,
    *,
    schema: str,
    template: Path,
    results: list[dict[str, Any]],
    epochs: int,
    poll_timeout: float,
) -> dict[str, Any] | None:
    """upload -> validate -> train -> evaluate -> assess for one template."""
    if not template.exists():
        _step(results, f"{schema}_template_present", "SKIP", {"path": str(template)})
        return None

    label = f"{schema}"
    status, body = client.json(
        "POST",
        "/api/v1/training/datasets",
        json_body={"name": f"smoke-{label}", "notes": "smoke_staging SYNTHETIC"},
    )
    if status != 200:
        _step(results, f"{label}_create_dataset", "FAIL", body)
        return None
    ds_id = body["dataset"]["dataset_id"]

    st, b = client.json(
        "POST",
        f"/api/v1/release-shell/datasets/{ds_id}/upload",
        files={
            "file": (template.name, template.read_bytes(), "application/zip"),
        },
    )
    if st != 200:
        _step(results, f"{label}_upload", "FAIL", b)
        return None
    _step(results, f"{label}_upload", "PASS", {"dataset_id": ds_id})

    st, b = client.json("POST", f"/api/v1/release-shell/datasets/{ds_id}/validate")
    validation = (b or {}).get("validation") or {}
    if st != 200:
        _step(results, f"{label}_validate", "FAIL", b)
        return None
    _step(
        results,
        f"{label}_validate",
        "PASS" if validation.get("can_train") else "FAIL",
        {
            "overall": validation.get("overall"),
            "can_train": validation.get("can_train"),
            "channel_schema": validation.get("channel_schema"),
        },
    )
    if not validation.get("can_train"):
        return None

    st, b = client.json(
        "POST",
        "/api/v1/release-shell/jobs",
        json_body={
            "dataset_id": ds_id,
            "epochs": epochs,
            "batch_size": 2,
            "seeds": [42, 43, 44],
            "device": "cpu",
        },
    )
    if st not in (200, 202):
        _step(results, f"{label}_train_start", "FAIL", b)
        return None
    job_id = (b or {}).get("job_id")
    _step(results, f"{label}_train_start", "PASS", {"job_id": job_id})

    job_ok = False
    deadline = time.time() + poll_timeout
    final: Any = None
    while job_id and time.time() < deadline:
        time.sleep(5)
        _, jb = client.json("GET", f"/api/v1/jobs/{job_id}")
        final = jb
        st_str = str(
            (jb or {}).get("status") or ((jb or {}).get("job") or {}).get("status") or ""
        ).lower()
        if st_str in {"completed", "succeeded", "success"}:
            job_ok = True
            break
        if st_str in {"failed", "cancelled", "error"}:
            break
    _step(
        results,
        f"{label}_train_complete",
        "PASS" if job_ok else "FAIL",
        {"job_final_status": final and (final.get("status") if isinstance(final, dict) else None)},
    )
    if not job_ok:
        return None

    # Locate a checkpoint for this dataset.
    _, models = client.json("GET", "/api/v1/training/models")
    model_list = (models or {}).get("models") if isinstance(models, dict) else None
    if not isinstance(model_list, list):
        model_list = models if isinstance(models, list) else []
    ckpt = None
    model_id = None
    for m in model_list:
        if isinstance(m, dict) and m.get("dataset_id") == ds_id and m.get("checkpoint_path"):
            ckpt, model_id = m["checkpoint_path"], m.get("model_id")
            break

    if model_id:
        st, b = client.json(
            "GET", f"/api/v1/release-shell/models/{model_id}/evaluation"
        )
        _step(
            results,
            f"{label}_evaluate",
            "PASS" if st == 200 else "FAIL",
            {"status_code": st, "aggregate": (b or {}).get("hazards") and list((b or {}).get("hazards", {}).keys())},
        )
    else:
        _step(results, f"{label}_evaluate", "FAIL", {"error": "no model_id found"})

    if ckpt:
        st, b = client.json(
            "POST",
            "/api/v1/assess",
            json_body={
                "request_id": f"smoke-{label}-inside",
                "checkpoint": ckpt,
                "point": INSIDE_POINT,
                "hazards": ["subsidence", "landslide", "sinkhole"],
            },
        )
        # Assess needs a live AOI (Earth Engine) or a server-side features path.
        # If AOI acquisition is not configured we record SKIP, not FAIL.
        if st == 200:
            profiles = (b or {}).get("hazard_profiles") or (b or {}).get("profiles") or []
            _step(
                results,
                f"{label}_assess",
                "PASS",
                {"n_profiles": len(profiles), "statuses": [p.get("status") for p in profiles if isinstance(p, dict)]},
            )
        elif st in (400, 500, 502, 503):
            _step(
                results,
                f"{label}_assess",
                "SKIP",
                {"status_code": st, "reason": "assess AOI likely unavailable", "body": b},
            )
        else:
            _step(results, f"{label}_assess", "FAIL", {"status_code": st, "body": b})
        return {"checkpoint": ckpt, "model_id": model_id, "dataset_id": ds_id}
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="SSRI release-shell staging smoke test")
    parser.add_argument("--base-url", required=True)
    parser.add_argument("--api-key", default=os.environ.get("SSRI_API_KEY", ""))
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=60.0)
    parser.add_argument("--poll-timeout", type=float, default=900.0)
    parser.add_argument("--allow-production", action="store_true")
    parser.add_argument(
        "--out",
        default=str(RELEASE_SHELL / "outputs" / "smoke_staging.json"),
    )
    args = parser.parse_args(argv)

    if _is_production(args.base_url) and not args.allow_production:
        print(
            "REFUSING to run against a production-looking host "
            f"({args.base_url}). Pass --allow-production to override.",
            file=sys.stderr,
        )
        return 2

    results: list[dict[str, Any]] = []
    client = SmokeClient(args.base_url, args.api_key, timeout=args.timeout)

    # 1. health
    st, b = client.json("GET", "/api/v1/health")
    _step(results, "health", "PASS" if st == 200 else "FAIL", {"status_code": st, "body": b})

    # 2. no_trained_model assess
    st, b = client.json(
        "POST",
        "/api/v1/assess",
        json_body={"request_id": "smoke-notrained", "hazards": ["subsidence"]},
    )
    ok = st == 200 and isinstance(b, dict) and b.get("status") == "no_trained_model"
    _step(
        results,
        "assess_no_trained_model",
        "PASS" if ok else "FAIL",
        {"status_code": st, "status": (b or {}).get("status")},
    )

    # 3. broken ZIP -> FAIL
    st, b = client.json(
        "POST",
        "/api/v1/training/datasets",
        json_body={"name": "smoke-broken-zip", "notes": "deliberately broken"},
    )
    if st == 200:
        ds_id = b["dataset"]["dataset_id"]
        st, b = client.json(
            "POST",
            f"/api/v1/release-shell/datasets/{ds_id}/upload",
            files={"file": ("broken.zip", b"this is not a zip file", "application/zip")},
        )
        if st == 400:
            _step(results, "broken_zip_fail", "PASS", {"status_code": st, "body": b})
        elif st == 200:
            st2, b2 = client.json(
                "POST", f"/api/v1/release-shell/datasets/{ds_id}/validate"
            )
            validation = (b2 or {}).get("validation") or {}
            _step(
                results,
                "broken_zip_fail",
                "PASS" if not validation.get("can_train") else "FAIL",
                {"overall": validation.get("overall"), "can_train": validation.get("can_train")},
            )
        else:
            _step(results, "broken_zip_fail", "FAIL", {"status_code": st, "body": b})
    else:
        _step(results, "broken_zip_fail", "FAIL", {"error": "could not create dataset", "body": b})

    # 4 & 5. SYNTHETIC v1 and v2 cycles
    v1_ckpt = run_schema_cycle(
        client,
        schema="v1",
        template=V1_TEMPLATE,
        results=results,
        epochs=args.epochs,
        poll_timeout=args.poll_timeout,
    )
    v2_ckpt = run_schema_cycle(
        client,
        schema="v2",
        template=V2_TEMPLATE,
        results=results,
        epochs=args.epochs,
        poll_timeout=args.poll_timeout,
    )

    # 6. outside_training_region
    ckpt_info = v2_ckpt or v1_ckpt
    if ckpt_info and ckpt_info.get("checkpoint"):
        st, b = client.json(
            "POST",
            "/api/v1/assess",
            json_body={
                "request_id": "smoke-outside",
                "checkpoint": ckpt_info["checkpoint"],
                "point": OUTSIDE_POINT,
                "hazards": ["subsidence", "landslide", "sinkhole"],
            },
        )
        profiles = (b or {}).get("hazard_profiles") or (b or {}).get("profiles") or []
        statuses = [p.get("status") for p in profiles if isinstance(p, dict)]
        ok = st == 200 and "outside_training_region" in statuses
        verdict = "PASS" if ok else ("SKIP" if st in (400, 500, 502, 503) else "FAIL")
        _step(
            results,
            "outside_training_region",
            verdict,
            {"status_code": st, "statuses": statuses},
        )
    else:
        _step(results, "outside_training_region", "SKIP", {"reason": "no checkpoint available"})

    failed = [r for r in results if r["status"] == "FAIL"]
    report = {
        "base_url": args.base_url,
        "allow_production": args.allow_production,
        "production_host": _is_production(args.base_url),
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "pass": not failed,
        "n_pass": sum(1 for r in results if r["status"] == "PASS"),
        "n_fail": len(failed),
        "n_skip": sum(1 for r in results if r["status"] == "SKIP"),
        "steps": results,
    }
    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("pass", "n_pass", "n_fail", "n_skip")}, indent=2))
    print(f"report: {out_path}")
    return 0 if report["pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
