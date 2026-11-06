"""Label-inventory upload and join onto a feature grid.

Accepts CSV or GeoJSON of georeferenced points (polygons: centroid used) with a
hazard column and optional date. Training refuses without labels.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.ml.constants import LABEL_NODATA
from ssri_model.release_shell.hazards import hazard_id_by_name, hazard_names
from ssri_model.release_shell.point_grid_csv import detect_delimiter, require_declared_crs


@dataclass
class LabelRecord:
    x: float
    y: float
    hazard: str
    class_id: int
    date: str | None = None


@dataclass
class LabelInventory:
    crs: str
    records: list[LabelRecord] = field(default_factory=list)
    counts_by_hazard: dict[str, int] = field(default_factory=dict)
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "crs": self.crs,
            "n_labels": len(self.records),
            "counts_by_hazard": dict(self.counts_by_hazard),
            "messages": list(self.messages),
        }


def _parse_hazard(raw: str) -> tuple[str, int]:
    key = (raw or "").strip().lower()
    ids = hazard_id_by_name()
    if key in ids:
        return key, ids[key]
    try:
        value = int(float(key))
    except ValueError as exc:
        raise ManualTrainingError(
            f"Unrecognised hazard label '{raw}'. "
            f"Use one of: {', '.join(hazard_names())} or class ids 0/1/2.",
            code="LABEL_HAZARD",
        ) from exc
    rev = {v: k for k, v in ids.items()}
    if value not in rev:
        raise ManualTrainingError(
            f"Hazard class id {value} is not in the registry.",
            code="LABEL_HAZARD",
        )
    return rev[value], value


def parse_label_csv(
    content: bytes,
    *,
    crs: str,
    filename: str = "labels.csv",
    hazard_column: str = "hazard",
    date_column: str | None = "date",
) -> LabelInventory:
    declared = require_declared_crs(crs)
    text = content.decode("utf-8-sig")
    delim = detect_delimiter("\n".join(text.splitlines()[:20]))
    reader = csv.DictReader(io.StringIO(text), delimiter=delim)
    if not reader.fieldnames:
        raise ManualTrainingError(f"{filename} needs a header row.", code="LABEL_HEADER")
    fields = {f.lower(): f for f in reader.fieldnames}
    for need in ("x", "y"):
        if need not in fields:
            raise ManualTrainingError(
                f"{filename} must include X and Y columns (found {list(reader.fieldnames)}).",
                code="LABEL_COLUMN",
            )
    haz_key = fields.get(hazard_column.lower()) or fields.get("label") or fields.get("class")
    if haz_key is None:
        raise ManualTrainingError(
            f"{filename} needs a hazard/label column.",
            code="LABEL_COLUMN",
        )
    date_key = fields.get((date_column or "").lower()) if date_column else None

    records: list[LabelRecord] = []
    counts = {n: 0 for n in hazard_names()}
    for row in reader:
        if not any((v or "").strip() for v in row.values()):
            continue
        x = float(row[fields["x"]])
        y = float(row[fields["y"]])
        name, cid = _parse_hazard(row[haz_key])
        date_raw = (row.get(date_key) or "").strip() if date_key else ""
        date = date_raw or None
        if date:
            try:
                datetime.fromisoformat(date.replace("Z", "+00:00"))
            except ValueError:
                # keep raw string; validator may WARN
                pass
        records.append(LabelRecord(x=x, y=y, hazard=name, class_id=cid, date=date))
        counts[name] = counts.get(name, 0) + 1

    if not records:
        raise ManualTrainingError(
            f"{filename} contains no labelled points. Training refuses without labels.",
            code="LABEL_EMPTY",
        )
    return LabelInventory(crs=declared, records=records, counts_by_hazard=counts)


def parse_label_geojson(content: bytes, *, crs: str, filename: str = "labels.geojson") -> LabelInventory:
    declared = require_declared_crs(crs)
    payload = json.loads(content.decode("utf-8"))
    features = payload.get("features") or []
    records: list[LabelRecord] = []
    counts = {n: 0 for n in hazard_names()}
    for feat in features:
        props = feat.get("properties") or {}
        geom = feat.get("geometry") or {}
        gtype = geom.get("type")
        coords = geom.get("coordinates")
        if gtype == "Point":
            x, y = float(coords[0]), float(coords[1])
        elif gtype == "Polygon":
            ring = coords[0]
            x = sum(p[0] for p in ring) / len(ring)
            y = sum(p[1] for p in ring) / len(ring)
        else:
            continue
        raw = props.get("hazard") or props.get("label") or props.get("class")
        if raw is None:
            continue
        name, cid = _parse_hazard(str(raw))
        date = props.get("date") or props.get("label_date")
        records.append(
            LabelRecord(x=x, y=y, hazard=name, class_id=cid, date=str(date) if date else None)
        )
        counts[name] = counts.get(name, 0) + 1
    if not records:
        raise ManualTrainingError(
            f"{filename} contains no labelled features. Training refuses without labels.",
            code="LABEL_EMPTY",
        )
    return LabelInventory(crs=declared, records=records, counts_by_hazard=counts)


def join_labels_to_grid(
    inventory: LabelInventory,
    xs: list[float],
    ys: list[float],
    *,
    x_spacing: float,
    y_spacing: float,
) -> tuple[dict[tuple[float, float], int], dict[str, int]]:
    """Snap labels to nearest grid cell; report per-hazard counts on-grid."""
    import numpy as np

    x_arr = np.asarray(xs, dtype=np.float64)
    y_arr = np.asarray(ys, dtype=np.float64)
    on_grid: dict[tuple[float, float], int] = {}
    counts = {n: 0 for n in hazard_names()}
    half_x, half_y = abs(x_spacing) / 2, abs(y_spacing) / 2
    for rec in inventory.records:
        # nearest grid node within half-cell
        ix = int(np.argmin(np.abs(x_arr - rec.x)))
        iy = int(np.argmin(np.abs(y_arr - rec.y)))
        if abs(x_arr[ix] - rec.x) > half_x or abs(y_arr[iy] - rec.y) > half_y:
            continue
        key = (round(float(x_arr[ix]), 8), round(float(y_arr[iy]), 8))
        on_grid[key] = rec.class_id
        counts[rec.hazard] = counts.get(rec.hazard, 0) + 1
    return on_grid, counts


def insufficient_label_message(counts: dict[str, int], *, min_per_hazard: int) -> list[str]:
    msgs = []
    for name in hazard_names():
        n = int(counts.get(name, 0))
        if n < min_per_hazard:
            msgs.append(
                f"insufficient labelled data for '{name}': found {n}, need ≥ {min_per_hazard}."
            )
    return msgs


EMPTY_LABEL_GRID_VALUE = LABEL_NODATA
