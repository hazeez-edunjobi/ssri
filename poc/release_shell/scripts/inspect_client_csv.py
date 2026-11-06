"""Inspect client CSV copy — SYNTHETIC tooling only; does not modify original."""

from __future__ import annotations

import csv
import json
import shutil
import statistics
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "sheet 260_Abeokuta.csv"
OUT_DIR = ROOT / "poc" / "release_shell" / "outputs" / "client_csv_inspect"
COPY = OUT_DIR / "260_abeokuta_COPY.csv"


def detect_delimiter(sample: str) -> str:
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;| ")
        return dialect.delimiter
    except csv.Error:
        # fallback counts
        counts = {d: sample.count(d) for d in [",", "\t", ";", " "]}
        return max(counts, key=counts.get)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    if not SRC.exists():
        raise SystemExit(f"missing source: {SRC}")
    shutil.copy2(SRC, COPY)

    raw = COPY.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    first_lines = text.splitlines()[:5]
    sample = "\n".join(text.splitlines()[:50])
    delim = detect_delimiter(sample)

    # stream parse
    xs: list[float] = []
    ys: list[float] = []
    zs: list[float] = []
    dups = 0
    seen: set[tuple[float, float]] = set()
    bad_rows = 0
    blank = 0
    header_row = None
    with COPY.open("r", encoding="utf-8-sig", newline="") as fh:
        # peek first row
        peek = fh.readline()
        fh.seek(0)
        parts = peek.strip().split(delim) if delim != " " else peek.split()
        has_header = False
        try:
            float(parts[0].replace(",", ""))
        except Exception:
            has_header = True
            header_row = [p.strip() for p in parts]

        reader = csv.reader(fh, delimiter=delim)
        if has_header:
            next(reader, None)
        for i, row in enumerate(reader, start=2 if has_header else 1):
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

    n = len(xs)
    ux = sorted(set(round(x, 8) for x in xs))
    uy = sorted(set(round(y, 8) for y in ys))
    x_gaps = [round(ux[i + 1] - ux[i], 8) for i in range(len(ux) - 1)]
    y_gaps = [round(uy[i + 1] - uy[i], 8) for i in range(len(uy) - 1)]
    x_gap_counts = Counter(x_gaps)
    y_gap_counts = Counter(y_gaps)
    expected_cells = len(ux) * len(uy)
    missing_cells = expected_cells - len(seen)

    # nodata / sentinel heuristics
    nodata_candidates = Counter()
    negative_z = 0
    sentinel_like = 0
    sentinel_values = {-9999.0, -9999, -999.0, -999, 9999.0, 9999, -32768.0, -32768}
    for z in zs:
        if z != z or z in sentinel_values:  # noqa: PLR0124
            nodata_candidates[str(z)] += 1
            sentinel_like += 1
        if z < 0:
            negative_z += 1

    # Histogram (fixed bins over observed Z range)
    z_min = min(zs) if zs else float("nan")
    z_max = max(zs) if zs else float("nan")
    n_bins = 20
    hist_counts = [0] * n_bins
    hist_edges: list[float] = []
    if zs and z_max > z_min:
        width = (z_max - z_min) / n_bins
        hist_edges = [z_min + i * width for i in range(n_bins + 1)]
        for z in zs:
            idx = int((z - z_min) / width)
            if idx >= n_bins:
                idx = n_bins - 1
            if idx < 0:
                idx = 0
            hist_counts[idx] += 1
    elif zs:
        hist_edges = [z_min, z_max]
        hist_counts = [len(zs)]

    # Gap spatial pattern: locate missing cells on the regular UX×UY lattice
    spacing_x = x_gap_counts.most_common(1)[0][0] if x_gap_counts else None
    spacing_y = y_gap_counts.most_common(1)[0][0] if y_gap_counts else None
    missing_coords: list[tuple[float, float]] = []
    if ux and uy:
        present = {(round(x, 8), round(y, 8)) for x, y in zip(xs, ys)}
        for y in uy:
            for x in ux:
                key = (round(x, 8), round(y, 8))
                if key not in present:
                    missing_coords.append((x, y))

    gap_pattern = "none"
    gap_clusters = 0
    gap_largest_component = 0
    gap_bbox = None
    gap_note = "No missing cells."
    if missing_coords and spacing_x and spacing_y:
        # 4-connected components on the lattice index grid
        x_index = {round(x, 8): i for i, x in enumerate(ux)}
        y_index = {round(y, 8): i for i, y in enumerate(uy)}
        missing_idx = {
            (x_index[round(x, 8)], y_index[round(y, 8)]) for x, y in missing_coords
        }
        seen_cc: set[tuple[int, int]] = set()
        components: list[list[tuple[int, int]]] = []
        for start in missing_idx:
            if start in seen_cc:
                continue
            stack = [start]
            comp: list[tuple[int, int]] = []
            seen_cc.add(start)
            while stack:
                cx, cy = stack.pop()
                comp.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    nb = (cx + dx, cy + dy)
                    if nb in missing_idx and nb not in seen_cc:
                        seen_cc.add(nb)
                        stack.append(nb)
            components.append(comp)
        gap_clusters = len(components)
        gap_largest_component = max(len(c) for c in components)
        mx = [x for x, _ in missing_coords]
        my = [y for _, y in missing_coords]
        gap_bbox = [min(mx), max(mx), min(my), max(my)]
        # Heuristic: clustered if few components hold most gaps
        frac_largest = gap_largest_component / len(missing_coords)
        if gap_clusters <= 5 or frac_largest >= 0.5:
            gap_pattern = "clustered"
            gap_note = (
                f"{len(missing_coords)} gaps in {gap_clusters} connected component(s); "
                f"largest holds {gap_largest_component} cells "
                f"({frac_largest:.0%}). Pattern consistent with AOI/mask edges "
                "or contiguous voids rather than random salt-and-pepper holes."
            )
        else:
            gap_pattern = "scattered"
            gap_note = (
                f"{len(missing_coords)} gaps in {gap_clusters} connected component(s); "
                f"largest holds {gap_largest_component} cells "
                f"({frac_largest:.0%}). Pattern is dispersed across the grid."
            )

    z_sorted = sorted(zs)
    def pct(p: float) -> float:
        if not z_sorted:
            return float("nan")
        idx = min(len(z_sorted) - 1, max(0, int(round((p / 100) * (len(z_sorted) - 1)))))
        return z_sorted[idx]

    report = {
        "source_path": str(SRC),
        "copy_path": str(COPY),
        "bytes": len(raw),
        "line_count_including_header_estimate": len(text.splitlines()),
        "data_rows": n,
        "delimiter_detected": repr(delim),
        "header_present": has_header,
        "header_row": header_row,
        "first_lines": first_lines,
        "columns": 3,
        "x_min": min(xs) if xs else None,
        "x_max": max(xs) if xs else None,
        "y_min": min(ys) if ys else None,
        "y_max": max(ys) if ys else None,
        "x_range": [min(xs), max(xs)] if xs else None,
        "y_range": [min(ys), max(ys)] if ys else None,
        "z_min": z_min if zs else None,
        "z_max": z_max if zs else None,
        "z_mean": statistics.fmean(zs) if zs else None,
        "z_range": [z_min, z_max] if zs else None,
        "z_stdev": statistics.pstdev(zs) if len(zs) > 1 else None,
        "z_p01": pct(1),
        "z_p50": pct(50),
        "z_p99": pct(99),
        "z_histogram": {
            "n_bins": len(hist_counts),
            "edges": hist_edges,
            "counts": hist_counts,
        },
        "negative_z_count": negative_z,
        "sentinel_like_count": sentinel_like,
        "nodata_candidate_counts": dict(nodata_candidates),
        "unique_x": len(ux),
        "unique_y": len(uy),
        "dominant_x_spacing": x_gap_counts.most_common(3),
        "dominant_y_spacing": y_gap_counts.most_common(3),
        "x_spacing_unique_count": len(x_gap_counts),
        "y_spacing_unique_count": len(y_gap_counts),
        "expected_full_grid_cells": expected_cells,
        "observed_unique_xy": len(seen),
        "missing_grid_cells": missing_cells,
        "gap_spatial_pattern": gap_pattern,
        "gap_connected_components": gap_clusters,
        "gap_largest_component_cells": gap_largest_component,
        "gap_bbox_xy": gap_bbox,
        "gap_note": gap_note,
        "duplicate_xy_rows": dups,
        "blank_rows": blank,
        "bad_rows": bad_rows,
        "crs": "UNKNOWN — not declared in file",
        "value_meaning": "UNKNOWN — client must confirm",
        "units": "UNKNOWN",
        "hypothesis_crs": {
            "status": "UNKNOWN",
            "note": (
                "Coordinates may belong to a Nigerian projected grid "
                "(possibly Transverse Mercator near 4.5E without false easting). "
                "Not confirmed."
            ),
        },
    }
    (OUT_DIR / "findings.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
