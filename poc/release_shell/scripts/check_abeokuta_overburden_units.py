"""ASSUMED-FOR-TEST: run the real Abeokuta CSV through the release-shell layer validator.

The CSV is declared as ``overburden_thickness`` with an ASSUMED-FOR-TEST CRS
(EPSG:32631 — NOT client-confirmed). Negative Z (11,250 values, min −212.76)
must surface a visible WARN/FAIL with a readable unit-sanity message.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs" / "abeokuta_overburden_unit_sanity.txt"
CSV = ROOT / "sheet 260_Abeokuta.csv"
ASSUMED_CRS = "EPSG:32631"  # ASSUMED-FOR-TEST — not client-confirmed


def main() -> int:
    sys.path.insert(0, str(ROOT / "model" / "src"))
    from ssri_model.release_shell.validator import validate_point_grid_layer

    if not CSV.exists():
        OUT.write_text(f"missing {CSV}\n", encoding="utf-8")
        print(OUT.read_text(encoding="utf-8"))
        return 1

    report = validate_point_grid_layer(
        CSV.read_bytes(),
        filename="sheet 260_Abeokuta.csv",
        layer_name="overburden_thickness",
        crs=ASSUMED_CRS,
    )
    lines = [
        "=== ABEOKUTA OVERBURDEN LAYER VALIDATION (ASSUMED-FOR-TEST) ===",
        f"assumed_crs={ASSUMED_CRS} (ASSUMED-FOR-TEST — not geological truth)",
        f"layer_name=overburden_thickness",
        f"overall={report['overall']}",
        f"status={report['status']}",
        f"trainable={report['trainable']}",
        f"row_count={report['row_count']}",
        f"missing_cells={report['missing_cells']}",
        f"value_min={report['value_min']}",
        f"value_max={report['value_max']}",
        "",
        "--- checks ---",
    ]
    for check in report["checks"]:
        lines.append(f"[{check['status']}] {check['name']}: {check['message']}")

    unit = next((c for c in report["checks"] if c["name"] == "unit_sanity"), None)
    flagged = bool(unit) and unit["status"] in {"WARN", "FAIL"} and "negative" in unit["message"].lower()
    lines += ["", f"unit_sanity_visible_warn_or_fail={flagged}"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    (OUT.parent / "abeokuta_overburden_unit_sanity.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(text)
    return 0 if flagged else 2


if __name__ == "__main__":
    raise SystemExit(main())

