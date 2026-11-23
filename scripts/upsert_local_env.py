"""Upsert hybrid local-stack SSRI_* keys into repo-root .env (no secret printing)."""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"


def upsert(text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(text):
        return pattern.sub(line, text)
    return text.rstrip() + "\n" + line + "\n"


def main() -> int:
    if not ENV_PATH.is_file():
        print("MISSING_ENV", ENV_PATH, file=sys.stderr)
        return 1
    text = ENV_PATH.read_text(encoding="utf-8")
    pw_m = re.search(r"^POSTGRES_PASSWORD=(.*)$", text, re.M)
    user_m = re.search(r"^POSTGRES_USER=(.*)$", text, re.M)
    db_m = re.search(r"^POSTGRES_DB=(.*)$", text, re.M)
    pw = (pw_m.group(1).strip() if pw_m else "change_me")
    user = (user_m.group(1).strip() if user_m else "ssri")
    db = (db_m.group(1).strip() if db_m else "ssri")

    out = (ROOT / "data" / "outputs").resolve()
    auth = (ROOT / "data" / "auth" / "keys.json").resolve()
    out.mkdir(parents=True, exist_ok=True)
    auth.parent.mkdir(parents=True, exist_ok=True)

    redis_url = "redis://127.0.0.1:6379/0"
    pairs = {
        "SSRI_API_ENVIRONMENT": "development",
        "SSRI_API_HOST": "127.0.0.1",
        "SSRI_API_PORT": "8000",
        "SSRI_API_OUTPUT_ROOT": out.as_posix(),
        "SSRI_EXECUTION_MODE": "distributed",
        "SSRI_DATABASE_URL": f"postgresql+psycopg://{user}:{pw}@127.0.0.1:5432/{db}",
        "SSRI_REDIS_URL": redis_url,
        "SSRI_CELERY_BROKER_URL": redis_url,
        "SSRI_CELERY_RESULT_BACKEND": redis_url,
        "SSRI_CELERY_CONCURRENCY": "1",
        # Stage-0 / Celery legacy keys — must not point at Docker DNS on the host.
        "REDIS_URL": redis_url,
        "CELERY_BROKER_URL": redis_url,
        "CELERY_RESULT_BACKEND": redis_url,
        "SSRI_AUTH_ENABLED": "false",
        "SSRI_AUTH_DEVELOPMENT_MODE": "true",
        "SSRI_AUTH_KEY_STORE": auth.as_posix(),
        "SSRI_DEMO_MODE": "false",
        "SSRI_ALLOW_FIXTURE_CHECKPOINTS": "false",
        "SSRI_API_ALLOW_UNVALIDATED_PREDICTIONS": "true",
        "SSRI_TRUST_CLIENT_SCIENTIFIC_STATUS": "true",
    }
    new = text
    for key, value in pairs.items():
        new = upsert(new, key, value)
    ENV_PATH.write_text(new, encoding="utf-8")
    print(f"UPDATED_KEYS={len(pairs)}")
    print(f"OUTPUT_ROOT={out.as_posix()}")
    print(f"AUTH_STORE={auth.as_posix()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
