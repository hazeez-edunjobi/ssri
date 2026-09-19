"""GEE init probe with path resolution and sanitized failure diagnostics."""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path


def _sanitize(text: str) -> str:
    text = re.sub(r"[A-Za-z]:\\\\[^\s'\"]+", "<path>", text)
    text = re.sub(r"/[^\s'\"]+\.(json|pem|key)", "<path>", text)
    text = re.sub(r"-----BEGIN[^-]+-----.*?-----END[^-]+-----", "<pem>", text, flags=re.S)
    text = re.sub(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+", "<email>", text)
    return text[:500]


def _resolve_credentials(repo: Path) -> Path | None:
    candidates: list[Path] = []
    for key in ("GOOGLE_APPLICATION_CREDENTIALS", "GEE_PRIVATE_KEY_PATH"):
        raw = os.getenv(key)
        if not raw:
            continue
        p = Path(raw)
        candidates.append(p)
        if not p.is_absolute():
            candidates.append(repo / p)
            candidates.append(repo / "credentials" / p.name)
    candidates.append(repo / "credentials" / "earth-engine.json")
    for path in candidates:
        if path.is_file():
            return path.resolve()
    return None


def main() -> int:
    repo = Path(__file__).resolve().parents[2]
    # Load .env if present without printing values.
    env_file = repo / ".env"
    if env_file.is_file():
        for line in env_file.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value

    creds = _resolve_credentials(repo)
    if creds is None:
        print("GEE_INIT=FAIL type=MissingCredentialsFile")
        print("DIAG=no_credentials_file_found")
        return 1
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(creds)
    if not os.getenv("GCP_PROJECT_ID") and os.getenv("GEE_PROJECT"):
        os.environ["GCP_PROJECT_ID"] = os.environ["GEE_PROJECT"]

    # Structural checks only (no secret material printed).
    try:
        payload = json.loads(creds.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"GEE_INIT=FAIL type=InvalidCredentialsJSON")
        print(f"DIAG={type(exc).__name__}")
        return 1

    client_email = str(payload.get("client_email") or "")
    env_sa = os.getenv("GEE_SERVICE_ACCOUNT") or ""
    project_id = os.getenv("GCP_PROJECT_ID") or os.getenv("GEE_PROJECT") or ""
    print(f"CREDS_BASENAME={creds.name}")
    print(f"CREDS_HAS_PRIVATE_KEY={'private_key' in payload}")
    print(f"CREDS_TYPE={payload.get('type', '')}")
    print(f"SA_MATCH={bool(client_email) and client_email == env_sa}")
    print(f"PROJECT_LEN={len(project_id)}")
    print(f"PROJECT_LOOKS_ID={bool(re.fullmatch(r'[a-z][a-z0-9-]{4,30}', project_id))}")

    try:
        from ssri_model.data.gee_client import GEEConfig, initialize

        # Force resolved path through config.
        cfg = GEEConfig(
            credentials_path=str(creds),
            service_account=env_sa or client_email,
            project_id=project_id,
        )
        initialize(cfg, force=True)
        print("GEE_INIT=OK")
        return 0
    except Exception as exc:
        print(f"GEE_INIT=FAIL type={type(exc).__name__}")
        cause = getattr(exc, "__cause__", None)
        if cause is not None:
            print(f"CAUSE_TYPE={type(cause).__name__}")
            print(f"CAUSE={_sanitize(str(cause))}")
        print(f"ERROR={_sanitize(str(exc))}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
