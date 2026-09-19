#!/usr/bin/env python3
"""Filter poetry-exported requirements to exclude CUDA/torch GPU packages."""

from __future__ import annotations

import sys
from pathlib import Path

SKIP_PREFIXES = ("torch", "nvidia-", "cuda-", "triton", "cupy")


def package_name(line: str) -> str:
    raw = line.split(";", 1)[0].split("[", 1)[0]
    for sep in ("===", "==", "!=", "<=", ">=", "<", ">", "~=", "="):
        if sep in raw:
            raw = raw.split(sep, 1)[0]
            break
    return raw.strip().lower()


def main() -> int:
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "/tmp/requirements.txt")
    dst = Path(sys.argv[2] if len(sys.argv) > 2 else "/tmp/requirements.cpu.txt")
    kept: list[str] = []
    for line in src.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#"):
            continue
        name = package_name(raw)
        if any(name == prefix or name.startswith(prefix) for prefix in SKIP_PREFIXES):
            continue
        kept.append(raw)
    dst.write_text("\n".join(kept) + "\n", encoding="utf-8")
    print(f"filtered requirements: {len(kept)} packages -> {dst}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
