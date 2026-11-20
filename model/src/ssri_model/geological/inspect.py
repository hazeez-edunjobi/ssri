"""Structural inspect for geological point-grid CSVs (no CRS required).

Lifted from the release-shell inspect script patterns; path-generic and
Abeokuta-agnostic. Missing cells stay unfilled; negatives are reported only.
"""

from __future__ import annotations

import statistics
from collections import Counter
from pathlib import Path
from typing import Any

from ssri_model.release_shell.point_grid_csv import detect_delimiter


def inspect_point_grid_bytes(content: bytes, *, filename: str = "layer.csv") -> dict[str, Any]:
    """Return a structural inspect report without mutating the upload."""
    text = content.decode("utf-8-sig", errors="replace")
    lines = text.splitlines()
    sample = "\n".join(lines[:50])
    delim = detect_delimiter(sample) if sample else ","

    import csv
    import io

    stream = io.StringIO(text)
    peek = stream.readline()
    stream.seek(0)
    parts = peek.strip().split(delim) if delim != " " else peek.split()
    has_header = False
    header_row: list[str] | None = None
    if parts:
        try:
            float(parts[0].replace(",", ""))
        except Exception:
            has_header = True
            header_row = [p.strip() for p in parts]

    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    dups = 0
    seen: set[tuple[float, float]] = set()
    bad_rows = 0
    blank = 0

    reader = csv.reader(stream, delimiter=delim)
    if has_header:
        next(reader, None)
    for row in reader:
        if not row or not any(c.strip() for c in row):
            blank += 1
            continue
        if len(row) < 3:
            bad_rows += 1
            continue
        try:
            x, y, z = float(row[0]), float(row[1]), float(row[2])
        except ValueError:
            bad_rows += 1
            continue
        key = (round(x, 8), round(y, 8))
        if key in seen:
            dups += 1
        else:
            seen.add(key)
        xs.append(x)
        ys.append(y)
        zs.append(z)

    ux = sorted({round(x, 8) for x in xs})
    uy = sorted({round(y, 8) for y in ys})
    x_gaps = [round(ux[i + 1] - ux[i], 8) for i in range(len(ux) - 1)]
    y_gaps = [round(uy[i + 1] - uy[i], 8) for i in range(len(uy) - 1)]
    x_gap_counts = Counter(x_gaps)
    y_gap_counts = Counter(y_gaps)
    expected_cells = len(ux) * len(uy) if ux and uy else 0
    missing_cells = expected_cells - len(seen) if expected_cells else None

    sentinel_values = {-9999.0, -999.0, 9999.0, -32768.0}
    nodata_candidates: Counter[str] = Counter()
    negative_z = 0
    for z in zs:
        if z != z or z in sentinel_values:  # noqa: PLR0124
            nodata_candidates[str(z)] += 1
        if z < 0:
            negative_z += 1

    spacing_x = x_gap_counts.most_common(1)[0][0] if x_gap_counts else None
    spacing_y = y_gap_counts.most_common(1)[0][0] if y_gap_counts else None
    regularity = "unknown"
    if spacing_x is not None and spacing_y is not None:
        regularity = (
            "regular"
            if len(x_gap_counts) == 1 and len(y_gap_counts) == 1
            else "irregular"
        )

    z_sorted = sorted(zs)

    def pct(p: float) -> float | None:
        if not z_sorted:
            return None
        idx = min(len(z_sorted) - 1, max(0, int(round((p / 100) * (len(z_sorted) - 1)))))
        return z_sorted[idx]

    suggested = {"x": 0, "y": 1, "z": 2}
    if header_row:
        lowered = {h.lower(): i for i, h in enumerate(header_row)}
        for names, key in (
            (("x", "lon", "longitude", "easting"), "x"),
            (("y", "lat", "latitude", "northing"), "y"),
            (("z", "value", "val", "thickness", "depth"), "z"),
        ):
            for name in names:
                if name in lowered:
                    suggested[key] = lowered[name]
                    break

    bbox = None
    if xs and ys:
        bbox = [min(xs), min(ys), max(xs), max(ys)]

    return {
        "overall": "INSPECTED",
        "filename": filename,
        "bytes": len(content),
        "delimiter": delim,
        "header_present": has_header,
        "header_row": header_row,
        "detected_columns": suggested,
        "row_count": len(xs),
        "bad_rows": bad_rows,
        "blank_rows": blank,
        "duplicate_xy": dups,
        "x_range": [min(xs), max(xs)] if xs else None,
        "y_range": [min(ys), max(ys)] if ys else None,
        "z_range": [min(zs), max(zs)] if zs else None,
        "z_stats": {
            "min": min(zs) if zs else None,
            "max": max(zs) if zs else None,
            "mean": statistics.fmean(zs) if zs else None,
            "stdev": statistics.pstdev(zs) if len(zs) > 1 else None,
            "p01": pct(1),
            "p50": pct(50),
            "p99": pct(99),
        },
        "negative_z_count": negative_z,
        "sentinel_like": dict(nodata_candidates),
        "unique_x": len(ux),
        "unique_y": len(uy),
        "dominant_spacing_x": spacing_x,
        "dominant_spacing_y": spacing_y,
        "grid_regularity_hint": regularity,
        "expected_full_grid_cells": expected_cells or None,
        "missing_lattice_cells": missing_cells,
        "coverage_bbox": bbox,
        "crs": None,
        "measurement_type": None,
        "units": None,
        "messages": [
            "CRS unknown until operator declaration.",
            "Measurement meaning unknown until operator declaration.",
            "Negatives are reported only; they are not auto-rejected at inspect.",
            "Missing lattice cells are not filled.",
        ],
    }


def inspect_point_grid_path(path: Path, *, filename: str | None = None) -> dict[str, Any]:
    return inspect_point_grid_bytes(
        path.read_bytes(), filename=filename or path.name
    )
