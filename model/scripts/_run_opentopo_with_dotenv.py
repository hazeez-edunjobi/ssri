"""Temporary helper: load repo .env then run OpenTopo qualify (no secrets printed)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

repo = Path(__file__).resolve().parents[2]
env_file = repo / ".env"
if env_file.is_file():
    for line in env_file.read_text(encoding="utf-8").splitlines():
        if not line or line.strip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key:
            os.environ[key] = value

print("OPENTOPO_KEY", "SET" if os.getenv("OPENTOPOGRAPHY_API_KEY") else "EMPTY")
sys.path.insert(0, str(Path(__file__).resolve().parent))
from qualify_opentopo_dem import main  # noqa: E402

raise SystemExit(main())
