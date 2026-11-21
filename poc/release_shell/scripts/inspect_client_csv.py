"""Inspect a client point-grid CSV — copies source, does not mutate original.

Delegates structural analysis to ``ssri_model.geological.inspect``.
Default path remains the Abeokuta candidate for offline operator use; pass
``--csv`` for any other file. Not a production assess input.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SRC = ROOT / "sheet 260_Abeokuta.csv"
OUT_DIR = ROOT / "poc" / "release_shell" / "outputs" / "client_csv_inspect"


def main() -> None:
    parser = argparse.ArgumentParser(description="Inspect geological point-grid CSV")
    parser.add_argument(
        "--csv",
        type=Path,
        default=DEFAULT_SRC,
        help="Source CSV path (copied; never mutated)",
    )
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=OUT_DIR,
        help="Directory for working copy + findings.json",
    )
    args = parser.parse_args()
    src: Path = args.csv
    out_dir: Path = args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    if not src.exists():
        raise SystemExit(f"missing source: {src}")

    copy = out_dir / f"{src.stem}_COPY{src.suffix}"
    shutil.copy2(src, copy)

    # Prefer package inspect when model src is on path
    sys.path.insert(0, str(ROOT / "model" / "src"))
    from ssri_model.geological.inspect import inspect_point_grid_path

    report = inspect_point_grid_path(copy, filename=src.name)
    report["source_path"] = str(src)
    report["copy_path"] = str(copy)
    (out_dir / "findings.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
