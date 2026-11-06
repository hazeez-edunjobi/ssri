"""Generic point-grid CSV ingest for release-shell feature layers.

Supports headerless or headed X/Y/value CSVs, delimiter detection, optional
column mapping, required CRS, streaming parse, and gap reporting.
Never silently fills missing grid cells.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from typing import Iterator

import numpy as np

from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.upload_limits import reject_if_upload_too_large, upload_max_rows
from ssri_model.ml.constants import FEATURE_NODATA
from ssri_model.release_shell.channel_schema import (
    OVERBURDEN_THICKNESS,
    normalize_layer_name,
)

try:
    from pyproj import CRS, Transformer
except ImportError:  # pragma: no cover — fall back to rasterio CRS for EPSG-only checks
    try:
        from rasterio.crs import CRS as _RioCRS

        class CRS:  # type: ignore
            @staticmethod
            def from_user_input(value: str):
                return _RioCRS.from_user_input(value)

        Transformer = None  # type: ignore
    except ImportError:
        CRS = None  # type: ignore
        Transformer = None  # type: ignore


@dataclass
class PointGridLayer:
    name: str
    crs: str
    working_crs: str
    x_spacing: float
    y_spacing: float
    xs: list[float]
    ys: list[float]
    values: dict[tuple[float, float], float]
    row_count: int
    missing_cells: int
    duplicates: int
    nodata_count: int
    value_min: float | None
    value_max: float | None
    status: str = "FEATURE_LAYER_ONLY"
    trainable: bool = False
    messages: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "crs": self.crs,
            "working_crs": self.working_crs,
            "x_spacing": self.x_spacing,
            "y_spacing": self.y_spacing,
            "grid": {"width": len(self.xs), "height": len(self.ys)},
            "row_count": self.row_count,
            "missing_cells": self.missing_cells,
            "duplicates": self.duplicates,
            "nodata_count": self.nodata_count,
            "value_min": self.value_min,
            "value_max": self.value_max,
            "status": self.status,
            "trainable": self.trainable,
            "messages": list(self.messages),
            "source_format": "point_grid_csv",
        }


def detect_delimiter(sample: str) -> str:
    try:
        return csv.Sniffer().sniff(sample, delimiters=",\t;| ").delimiter
    except csv.Error:
        counts = {d: sample.count(d) for d in [",", "\t", ";", " "]}
        return max(counts, key=counts.get) or ","


def require_declared_crs(crs: str | None) -> str:
    value = (crs or "").strip()
    if not value:
        raise ManualTrainingError(
            "CRS is required for every uploaded layer. "
            "Provide an EPSG code (for example EPSG:32631) or a full WKT/PROJ definition. "
            "Validation FAILS without a declared CRS.",
            code="CRS_REQUIRED",
        )
    if CRS is None:
        raise ManualTrainingError(
            "pyproj is required to validate CRS declarations.",
            code="CRS_BACKEND",
        )
    try:
        CRS.from_user_input(value)
    except Exception as exc:
        raise ManualTrainingError(
            f"CRS '{value}' could not be parsed. Use an EPSG code or full WKT.",
            code="CRS_INVALID",
        ) from exc
    return value


def _key(v: float) -> float:
    return round(float(v), 8)


def iter_xyv_rows(
    content: bytes,
    *,
    filename: str = "layer.csv",
    delimiter: str | None = None,
    has_header: bool | None = None,
    x_column: str | int | None = None,
    y_column: str | int | None = None,
    value_column: str | int | None = None,
) -> Iterator[tuple[float, float, float]]:
    """Yield (x, y, value) streaming; respects SSRI_UPLOAD_MAX_ROWS."""
    reject_if_upload_too_large(len(content))
    try:
        stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline="")
    except Exception as exc:
        raise ManualTrainingError(
            f"{filename} is not valid UTF-8 text.",
            code="CSV_ENCODING",
        ) from exc

    sample = stream.read(4096)
    stream.seek(0)
    delim = delimiter or detect_delimiter(sample)
    reader = csv.reader(stream, delimiter=delim)
    first = next(reader, None)
    if first is None:
        raise ManualTrainingError(f"{filename} is empty.", code="CSV_EMPTY")

    def _is_number(tok: str) -> bool:
        try:
            float(tok)
            return True
        except ValueError:
            return False

    header_mode = has_header
    if header_mode is None:
        header_mode = not all(_is_number(c.strip()) for c in first[:3] if c.strip())

    headers = [c.strip() for c in first] if header_mode else None
    rows_source: Iterator[list[str]]
    if header_mode:
        rows_source = reader
    else:
        def _chain() -> Iterator[list[str]]:
            yield first
            yield from reader

        rows_source = _chain()

    def _resolve(col: str | int | None, default_idx: int, default_names: tuple[str, ...]) -> str | int:
        if col is not None:
            return col
        if headers:
            lowered = {h.lower(): h for h in headers}
            for name in default_names:
                if name in lowered:
                    return lowered[name]
            return default_idx
        return default_idx

    x_spec = _resolve(x_column, 0, ("x", "lon", "longitude", "easting"))
    y_spec = _resolve(y_column, 1, ("y", "lat", "latitude", "northing"))
    z_spec = _resolve(value_column, 2, ("z", "value", "val", "thickness", "depth"))

    def _get(row: list[str], spec: str | int) -> str:
        if isinstance(spec, int):
            if spec >= len(row):
                raise ManualTrainingError(
                    f"{filename} row is missing column index {spec}.",
                    code="CSV_COLUMN",
                )
            return row[spec]
        if headers is None:
            raise ManualTrainingError(
                f"{filename} has no header; cannot select column '{spec}' by name.",
                code="CSV_COLUMN",
            )
        try:
            idx = headers.index(spec)
        except ValueError as exc:
            # case-insensitive
            lowered = [h.lower() for h in headers]
            if spec.lower() in lowered:
                idx = lowered.index(spec.lower())
            else:
                raise ManualTrainingError(
                    f"{filename} is missing column '{spec}'.",
                    code="CSV_COLUMN",
                ) from exc
        return row[idx]

    max_rows = upload_max_rows()
    yielded = 0
    for index, row in enumerate(rows_source, start=1):
        if max_rows is not None and index > max_rows:
            raise ManualTrainingError(
                f"{filename} has more than {max_rows} data rows. "
                "Split the grid or raise SSRI_UPLOAD_MAX_ROWS.",
                code="CSV_TOO_LARGE",
            )
        if not row or not any(c.strip() for c in row):
            continue
        try:
            x = float(_get(row, x_spec).strip())
            y = float(_get(row, y_spec).strip())
            raw = _get(row, z_spec).strip()
            z = FEATURE_NODATA if raw == "" else float(raw)
        except ManualTrainingError:
            raise
        except ValueError as exc:
            raise ManualTrainingError(
                f"{filename} row {index} has a non-numeric X/Y/value.",
                code="CSV_NUMBER",
            ) from exc
        yielded += 1
        yield x, y, z
    if yielded == 0:
        raise ManualTrainingError(f"{filename} has no data rows.", code="CSV_EMPTY")


def _spacing(values: list[float], *, axis: str) -> float:
    if len(values) < 2:
        raise ManualTrainingError(
            f"Need at least two distinct {axis} values to form a grid.",
            code="CSV_GRID",
        )
    gaps = [round(values[i + 1] - values[i], 8) for i in range(len(values) - 1)]
    unique = sorted(set(gaps))
    if len(unique) != 1:
        raise ManualTrainingError(
            f"Irregular {axis} spacing detected: {unique[:6]}. "
            "SSRI does not interpolate irregular point clouds.",
            code="CSV_GRID",
        )
    if unique[0] == 0:
        raise ManualTrainingError(f"Zero {axis} spacing.", code="CSV_GRID")
    return float(unique[0])


def ingest_point_grid_csv(
    content: bytes,
    *,
    filename: str,
    layer_name: str,
    crs: str,
    working_crs: str | None = None,
    delimiter: str | None = None,
    has_header: bool | None = None,
    x_column: str | int | None = None,
    y_column: str | int | None = None,
    value_column: str | int | None = None,
    nodata_values: set[float] | None = None,
) -> PointGridLayer:
    """Parse a single-value spatial CSV into a regular grid description.

    Always returns FEATURE_LAYER_ONLY — a single layer cannot supervise training.
    """
    declared = require_declared_crs(crs)
    work = require_declared_crs(working_crs or declared)
    name = normalize_layer_name(layer_name) or normalize_layer_name(filename)

    sentinels = set(nodata_values or {FEATURE_NODATA, -9999.0, -999.0})
    points: dict[tuple[float, float], float] = {}
    duplicates = 0
    nodata_count = 0
    row_count = 0
    finite_vals: list[float] = []

    transformer = None
    if work != declared:
        if Transformer is None:
            raise ManualTrainingError("pyproj is required for reprojection.", code="CRS_BACKEND")
        transformer = Transformer.from_crs(declared, work, always_xy=True)

    for x, y, z in iter_xyv_rows(
        content,
        filename=filename,
        delimiter=delimiter,
        has_header=has_header,
        x_column=x_column,
        y_column=y_column,
        value_column=value_column,
    ):
        row_count += 1
        if transformer is not None:
            x, y = transformer.transform(x, y)
        key = (_key(x), _key(y))
        if key in points:
            duplicates += 1
            continue
        if z in sentinels or z != z:  # noqa: PLR0124
            nodata_count += 1
            points[key] = FEATURE_NODATA
        else:
            points[key] = float(z)
            finite_vals.append(float(z))

    xs = sorted({p[0] for p in points})
    ys = sorted({p[1] for p in points})
    x_spacing = _spacing(xs, axis="X")
    y_spacing = _spacing(ys, axis="Y")
    expected = len(xs) * len(ys)
    missing = expected - len(points)

    messages = [
        "This upload is a single feature layer only. "
        "It cannot be used alone as a supervised training dataset. "
        "Add the remaining SSRI channels (or schema v2 extras) and labelled hazards to train.",
    ]
    if missing:
        messages.append(
            f"Grid has {missing} missing cell(s). SSRI does not fill gaps; "
            "provide complete cells or a mask before training."
        )
    if duplicates:
        messages.append(f"Skipped {duplicates} duplicate X/Y row(s); first value kept.")

    # Unit sanity: thickness cannot be negative (depth-to-bedrock is a different name).
    if name == OVERBURDEN_THICKNESS and finite_vals:
        negative_n = sum(1 for v in finite_vals if v < 0)
        if negative_n:
            messages.append(
                f"UNIT_SANITY WARN: {negative_n} negative value(s) in layer "
                f"'{OVERBURDEN_THICKNESS}'. Thickness should be ≥ 0 metres; "
                "confirm units and whether negatives are sentinels. "
                "If this is depth-to-bedrock, declare that name instead — "
                "SSRI will not silently relabel it as overburden_thickness."
            )

    return PointGridLayer(
        name=name,
        crs=declared,
        working_crs=work,
        x_spacing=x_spacing,
        y_spacing=y_spacing,
        xs=xs,
        ys=ys,
        values=points,
        row_count=row_count,
        missing_cells=missing,
        duplicates=duplicates,
        nodata_count=nodata_count,
        value_min=min(finite_vals) if finite_vals else None,
        value_max=max(finite_vals) if finite_vals else None,
        status="FEATURE_LAYER_ONLY",
        trainable=False,
        messages=messages,
    )


def layer_to_array(layer: PointGridLayer) -> np.ndarray:
    """Rasterise layer values onto its regular grid (nodata for gaps)."""
    height, width = len(layer.ys), len(layer.xs)
    y_to_row = {_key(y): i for i, y in enumerate(reversed(layer.ys))}
    x_to_col = {_key(x): i for i, x in enumerate(layer.xs)}
    out = np.full((height, width), FEATURE_NODATA, dtype=np.float64)
    for (x, y), value in layer.values.items():
        out[y_to_row[y], x_to_col[x]] = value
    return out
