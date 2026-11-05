"""ASSUMED-FOR-TEST: run Abeokuta CSV as overburden_thickness through point-grid ingest."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
OUT = Path(__file__).resolve().parents[1] / "outputs" / "abeokuta_overburden_unit_sanity.txt"
CSV = ROOT / "sheet 260_Abeokuta.csv"


def main() -> int:
    sys.path.insert(0, str(ROOT / "model" / "src"))
    from ssri_model.release_shell.point_grid_csv import ingest_point_grid_csv

    if not CSV.exists():
        OUT.write_text(f"missing {CSV}\n", encoding="utf-8")
        print(OUT.read_text(encoding="utf-8"))
        return 1

    layer = ingest_point_grid_csv(
        CSV.read_bytes(),
        filename="sheet 260_Abeokuta.csv",
        layer_name="overburden_thickness",
        crs="EPSG:32631",  # ASSUMED-FOR-TEST — not client-confirmed
    )
    lines = [
        f"status={layer.status}",
        f"trainable={layer.trainable}",
        f"value_min={layer.value_min}",
        f"value_max={layer.value_max}",
        f"row_count={layer.row_count}",
        f"missing_cells={layer.missing_cells}",
        "ASSUMED_CRS=EPSG:32631 (ASSUMED-FOR-TEST — not geological truth)",
        "layer_name=overburden_thickness",
    ]
    for m in layer.messages:
        lines.append(f"MSG: {m}")
    flagged = any("UNIT_SANITY" in m and "negative" in m.lower() for m in layer.messages)
    lines.append(f"unit_sanity_negative_flagged={flagged}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    text = "\n".join(lines) + "\n"
    OUT.write_text(text, encoding="utf-8")
    print(text)
    return 0 if flagged else 2


if __name__ == "__main__":
    raise SystemExit(main())
