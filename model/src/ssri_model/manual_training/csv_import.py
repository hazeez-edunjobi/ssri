"""Convert a spatial CSV into the existing Stage 2.5 training dataset.

The trainer is unchanged. A CSV is parsed, rebuilt as a regular grid, and
written as feature_stack.npy / label.tif samples. A single X,Y,Z file is a
feature layer and is not a supervised training dataset.
"""

from __future__ import annotations

import csv
import io
import json
import re
import zipfile
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import rasterio
from rasterio.transform import Affine

from ssri_model.dataset.catalog import write_manifest, write_statistics
from ssri_model.manual_training.exceptions import ManualTrainingError
from ssri_model.manual_training.upload_limits import reject_if_upload_too_large, upload_max_rows
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA, LABEL_NODATA
from ssri_model.ml.labels import label_class_names
from ssri_model.ml.splits import DatasetSplit

TILE = 16
MIN_TILE = 8

CHANNEL_ALIASES = {
    "elevation": "elevation",
    "slope": "slope",
    "curvature_1": "plan_curvature",
    "plan_curvature": "plan_curvature",
    "curvature_2": "profile_curvature",
    "profile_curvature": "profile_curvature",
    "wetness": "twi",
    "twi": "twi",
    "relief": "relative_relief",
    "relative_relief": "relative_relief",
    "valley_depth": "valley_depth",
    "vegetation": "ndvi",
    "ndvi": "ndvi",
    "water": "ndwi",
    "ndwi": "ndwi",
    "clay": "clay_mineral_ratio",
    "clay_mineral_ratio": "clay_mineral_ratio",
    "iron_oxide": "iron_oxide_index",
    "iron_oxide_index": "iron_oxide_index",
    "gravity": "gravity",
    "magnetics": "magnetics",
}

LABEL_NAMES = {
    "subsidence": 0,
    "landslide": 1,
    "sinkhole": 2,
    "nodata": LABEL_NODATA,
    "no_data": LABEL_NODATA,
    "no-data": LABEL_NODATA,
}


class CsvFeatureOnly(ManualTrainingError):
    """Parsed spatial CSV that cannot supervise the 13-channel model."""

    def __init__(self, message: str, *, analysis: dict) -> None:
        super().__init__(message, code="CSV_NOT_TRAINABLE")
        self.analysis = analysis


def looks_like_csv_bundle(filename: str, content: bytes) -> bool:
    if not filename.lower().endswith(".zip"):
        return False
    if not zipfile.is_zipfile(io.BytesIO(content)):
        return False
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        names = [item.replace("\\", "/") for item in archive.namelist() if not item.endswith("/")]
    lowered = [name.lower() for name in names]
    if any(name.endswith("manifest.json") for name in lowered):
        return False
    return any(name.endswith(".csv") for name in lowered)


def require_crs(crs: str) -> str:
    value = (crs or "").strip()
    if not value:
        raise ManualTrainingError(
            "CRS is required for this CSV because X/Y values are projected coordinates. "
            "Provide a code such as EPSG:32631.",
            code="CRS_REQUIRED",
        )
    if re.fullmatch(r"EPSG:\d+", value, flags=re.IGNORECASE):
        return value.upper()
    if re.fullmatch(r"[A-Za-z0-9_:+.-]{2,64}", value):
        return value
    raise ManualTrainingError(
        f"CRS '{value}' is not a recognized identifier. Use a code such as EPSG:32631.",
        code="CRS_INVALID",
    )


def convert_csv_dataset(
    dataset_root: Path,
    *,
    filename: str,
    content: bytes,
    crs: str,
    dataset_name: str,
) -> dict:
    """Write a Stage 2.5 tree under ``dataset_root`` and return conversion analysis."""
    reject_if_upload_too_large(len(content))
    declared_crs = require_crs(crs)
    tables = _read_table_blobs(filename, content)
    kind, layers, labels, rows = _interpret_blobs(tables)
    xs, ys, x_spacing, y_spacing = _grid_axes(layers[next(iter(layers))])
    _align_layers(layers, labels, xs, ys)
    analysis = _analysis(
        kind=kind,
        rows=rows,
        xs=xs,
        ys=ys,
        x_spacing=x_spacing,
        y_spacing=y_spacing,
        crs=declared_crs,
        layers=layers,
        labels=labels,
    )
    if kind == "single_layer" or labels is None or set(layers) != set(CHANNEL_NAMES):
        missing = [name for name in CHANNEL_NAMES if name not in layers]
        analysis["status"] = "FEATURE_LAYER_ONLY"
        analysis["trainable"] = False
        analysis["missing_features"] = missing
        message = (
            "Training labels are missing. "
            if labels is None
            else "This CSV does not contain every SSRI feature channel. "
        )
        message += (
            "A feature-only CSV can be imported as a spatial feature layer, "
            "but it cannot be used as a supervised training dataset."
        )
        if missing:
            message += " Missing: " + ", ".join(missing) + "."
        raise CsvFeatureOnly(message, analysis=analysis)

    stack, label_grid = _stack_grids(layers, labels, xs, ys)
    split = _write_tiles(
        dataset_root,
        stack=stack,
        labels=label_grid,
        xs=xs,
        ys=ys,
        x_spacing=x_spacing,
        y_spacing=y_spacing,
        crs=declared_crs,
    )
    write_statistics(dataset_root, split=split)
    write_manifest(
        dataset_root,
        dataset_name=dataset_name,
        version="csv-1",
        split=split,
        crs=declared_crs,
        resolution_m=float((abs(x_spacing) + abs(y_spacing)) / 2),
    )
    manifest_path = dataset_root / "manifest.json"
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    payload["source_format"] = "csv"
    payload["conversion"] = {
        "crs": declared_crs,
        "x_spacing": x_spacing,
        "y_spacing": y_spacing,
        "grid_width": len(xs),
        "grid_height": len(ys),
        "label_mapping": {
            "subsidence": 0,
            "landslide": 1,
            "sinkhole": 2,
            "nodata": LABEL_NODATA,
        },
    }
    manifest_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    analysis["status"] = "READY"
    analysis["trainable"] = True
    analysis["train_count"] = len(split.train)
    analysis["validation_count"] = len(split.validation)
    return analysis


def _read_table_blobs(filename: str, content: bytes) -> list[tuple[str, bytes]]:
    if filename.lower().endswith(".zip"):
        tables: list[tuple[str, bytes]] = []
        with zipfile.ZipFile(io.BytesIO(content)) as archive:
            for info in archive.infolist():
                if info.is_dir() or not info.filename.lower().endswith(".csv"):
                    continue
                name = Path(info.filename).name
                if ".." in Path(info.filename).parts:
                    raise ManualTrainingError(
                        f"CSV entry '{info.filename}' uses an unsafe path.",
                        code="UNSAFE_PATH",
                    )
                tables.append((Path(name).stem, archive.read(info)))
        if not tables:
            raise ManualTrainingError("The zip does not contain a CSV layer.", code="CSV_EMPTY")
        return tables
    return [(Path(filename).stem, content)]


def iter_csv_rows(filename: str, content: bytes):
    """Yield cleaned CSV data rows one at a time (streaming; no full-row list).

    SYNTHETIC and production uploads share this path. Row count is limited only
    when ``SSRI_UPLOAD_MAX_ROWS`` is set; default is unlimited.
    """
    try:
        stream = io.TextIOWrapper(io.BytesIO(content), encoding="utf-8-sig", newline="")
    except Exception as exc:  # pragma: no cover - BytesIO wrapper is reliable
        raise ManualTrainingError(
            f"{filename} is not valid UTF-8 text.",
            code="CSV_ENCODING",
        ) from exc
    reader = csv.DictReader(stream)
    if not reader.fieldnames:
        raise ManualTrainingError(
            f"{filename} needs a header row. Expected columns such as X, Y, and the SSRI features.",
            code="CSV_HEADER",
        )
    max_rows = upload_max_rows()
    yielded = 0
    try:
        for index, row in enumerate(reader, start=1):
            if max_rows is not None and index > max_rows:
                raise ManualTrainingError(
                    f"{filename} has more than {max_rows} data rows. "
                    "Split the grid, upload a smaller area, or raise SSRI_UPLOAD_MAX_ROWS.",
                    code="CSV_TOO_LARGE",
                )
            if not any((value or "").strip() for value in row.values()):
                continue
            yielded += 1
            yield {(key or "").strip(): (value or "").strip() for key, value in row.items()}
    except UnicodeDecodeError as exc:
        raise ManualTrainingError(
            f"{filename} is not valid UTF-8 text.",
            code="CSV_ENCODING",
        ) from exc
    if yielded == 0:
        raise ManualTrainingError(f"{filename} has a header but no data rows.", code="CSV_EMPTY")


def _interpret_blobs(
    tables: list[tuple[str, bytes]],
) -> tuple[str, dict[str, dict[tuple[float, float], float]], dict[tuple[float, float], int] | None, int]:
    if len(tables) == 1:
        name, blob = tables[0]
        return _interpret_single_blob(name, blob)

    layers: dict[str, dict[tuple[float, float], float]] = {}
    labels: dict[tuple[float, float], int] | None = None
    total = 0
    for name, blob in tables:
        key = name.lower()
        row_iter = iter_csv_rows(f"{name}.csv", blob)
        first = next(row_iter)
        mapping = _column_map(first)
        if key in {"label", "labels"}:
            labels, count = _labels_stream(first, row_iter, mapping)
            total += count
            continue
        if key not in CHANNEL_ALIASES and "z" in mapping and key not in CHANNEL_ALIASES:
            raise ManualTrainingError(
                f"CSV layer '{name}.csv' does not match an SSRI feature. "
                "Name the file after a feature, for example elevation.csv.",
                code="CSV_LAYER",
            )
        channel = CHANNEL_ALIASES.get(key, key)
        if "z" not in mapping:
            raise ManualTrainingError(
                f"{name}.csv must use X,Y,Z columns.",
                code="CSV_COLUMN",
            )
        points, count = _points_stream(first, row_iter, mapping, "z", filename=name)
        layers[channel] = points
        total += count
    return "multi_layer", layers, labels, total


def _interpret_single_blob(
    name: str,
    blob: bytes,
) -> tuple[str, dict[str, dict[tuple[float, float], float]], dict[tuple[float, float], int] | None, int]:
    row_iter = iter_csv_rows(f"{name}.csv" if not name.endswith(".csv") else name, blob)
    first = next(row_iter)
    mapping = _column_map(first)
    features = [channel for channel in CHANNEL_NAMES if channel in mapping]
    if features:
        layers, labels, count = _multi_feature_stream(first, row_iter, mapping, features)
        return "multi_feature", layers, labels, count
    if "z" not in mapping:
        raise ManualTrainingError(
            "CSV is missing required feature values. Use a Z column or the SSRI feature columns.",
            code="CSV_COLUMN",
        )
    layer_name = CHANNEL_ALIASES.get(name.lower(), name)
    points, count = _points_stream(first, row_iter, mapping, "z", filename=name)
    return "single_layer", {layer_name: points}, None, count


def _multi_feature_stream(
    first: dict[str, str],
    rest,
    mapping: dict[str, str],
    features: list[str],
) -> tuple[dict[str, dict[tuple[float, float], float]], dict[tuple[float, float], int] | None, int]:
    layers = {channel: {} for channel in features}
    labels: dict[tuple[float, float], int] | None = {} if "label" in mapping else None
    count = 0
    for index, row in enumerate(_chain_rows(first, rest), start=2):
        count += 1
        x = _number(row.get(mapping["x"], ""), filename="features", row_number=index, column="X")
        y = _number(row.get(mapping["y"], ""), filename="features", row_number=index, column="Y")
        key = (_key(x), _key(y))
        for channel in features:
            raw = row.get(mapping[channel], "")
            value = FEATURE_NODATA if raw == "" else _number(
                raw, filename="features", row_number=index, column=channel
            )
            if key in layers[channel]:
                raise ManualTrainingError(
                    f"Duplicate spatial coordinate detected: X={x}, Y={y}.",
                    code="CSV_DUPLICATE",
                )
            layers[channel][key] = value
        if labels is not None:
            if key in labels:
                raise ManualTrainingError(
                    f"Duplicate spatial coordinate detected: X={x}, Y={y}.",
                    code="CSV_DUPLICATE",
                )
            labels[key] = _label_value(row.get(mapping["label"], "").strip(), row_number=index)
    return layers, labels, count


def _chain_rows(first: dict[str, str], rest):
    yield first
    yield from rest


def _points_stream(
    first: dict[str, str],
    rest,
    mapping: dict[str, str],
    value_key: str,
    *,
    filename: str,
) -> tuple[dict[tuple[float, float], float], int]:
    points: dict[tuple[float, float], float] = {}
    count = 0
    for index, row in enumerate(_chain_rows(first, rest), start=2):
        count += 1
        x = _number(row.get(mapping["x"], ""), filename=filename, row_number=index, column="X")
        y = _number(row.get(mapping["y"], ""), filename=filename, row_number=index, column="Y")
        raw = row.get(mapping[value_key], "")
        value = FEATURE_NODATA if raw == "" else _number(
            raw, filename=filename, row_number=index, column=value_key
        )
        key = (_key(x), _key(y))
        if key in points:
            raise ManualTrainingError(
                f"Duplicate spatial coordinate detected: X={x}, Y={y}.",
                code="CSV_DUPLICATE",
            )
        points[key] = value
    return points, count


def _labels_stream(
    first: dict[str, str],
    rest,
    mapping: dict[str, str],
) -> tuple[dict[tuple[float, float], int], int]:
    column = mapping.get("label", mapping.get("z", "Z"))
    if "label" not in mapping and "z" in mapping:
        mapping = {**mapping, "label": mapping["z"]}
        column = mapping["label"]
    labels: dict[tuple[float, float], int] = {}
    count = 0
    for index, row in enumerate(_chain_rows(first, rest), start=2):
        count += 1
        x = _number(row.get(mapping["x"], ""), filename="labels", row_number=index, column="X")
        y = _number(row.get(mapping["y"], ""), filename="labels", row_number=index, column="Y")
        raw = row.get(column, "").strip()
        key = (_key(x), _key(y))
        if key in labels:
            raise ManualTrainingError(
                f"Duplicate spatial coordinate detected: X={x}, Y={y}.",
                code="CSV_DUPLICATE",
            )
        labels[key] = _label_value(raw, row_number=index)
    return labels, count


def _column_map(row: dict[str, str]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for original in row:
        key = original.strip().lower()
        if key in {"x", "y", "z", "label"}:
            mapping[key] = original
        elif key in CHANNEL_ALIASES:
            mapping[CHANNEL_ALIASES[key]] = original
        elif key:
            raise ManualTrainingError(
                f"CSV has an unrecognized column: {original}.",
                code="CSV_COLUMN",
            )
    if "x" not in mapping or "y" not in mapping:
        missing = "X" if "x" not in mapping else "Y"
        raise ManualTrainingError(
            f"CSV is missing required spatial column: {missing}.",
            code="CSV_COLUMN",
        )
    return mapping


def _label_value(raw: str, *, row_number: int) -> int:
    if raw == "":
        return LABEL_NODATA
    named = LABEL_NAMES.get(raw.lower())
    if named is not None:
        return named
    try:
        value = int(float(raw))
    except ValueError as exc:
        raise ManualTrainingError(
            f"Row {row_number} has an invalid label '{raw}'. "
            "Use 0 subsidence, 1 landslide, 2 sinkhole, or -1 nodata.",
            code="CSV_LABEL",
        ) from exc
    if value in {0, 1, 2, LABEL_NODATA}:
        return value
    raise ManualTrainingError(
        f"Row {row_number} has label {value}. "
        "SSRI labels are 0 subsidence, 1 landslide, 2 sinkhole, and -1 nodata.",
        code="CSV_LABEL",
    )


def _grid_axes(
    points: dict[tuple[float, float], float],
) -> tuple[list[float], list[float], float, float]:
    xs = sorted({point[0] for point in points})
    ys = sorted({point[1] for point in points})
    if len(xs) < 2 or len(ys) < 2:
        raise ManualTrainingError(
            "The CSV does not form a two-dimensional grid. At least two distinct X and Y values are required.",
            code="CSV_GRID",
        )
    x_spacing = _spacing(xs, axis="X")
    y_spacing = _spacing(ys, axis="Y")
    expected = len(xs) * len(ys)
    if len(points) != expected:
        raise ManualTrainingError(
            f"The spatial grid is missing {expected - len(points)} cells. "
            "SSRI does not fill or interpolate missing coordinates.",
            code="CSV_GRID",
        )
    return xs, ys, x_spacing, y_spacing


def _spacing(values: list[float], *, axis: str) -> float:
    gaps = [round(values[index + 1] - values[index], 8) for index in range(len(values) - 1)]
    unique = sorted(set(gaps))
    if len(unique) != 1:
        raise ManualTrainingError(
            f"The spatial grid is irregular. Expected consistent {axis} spacing "
            f"but detected multiple {axis} intervals: {unique[:4]}.",
            code="CSV_GRID",
        )
    if unique[0] == 0:
        raise ManualTrainingError(
            f"The spatial grid has zero {axis} spacing.",
            code="CSV_GRID",
        )
    return float(unique[0])


def _align_layers(
    layers: dict[str, dict[tuple[float, float], float]],
    labels: dict[tuple[float, float], int] | None,
    xs: list[float],
    ys: list[float],
) -> None:
    expected = {(_key(x), _key(y)) for x in xs for y in ys}
    for name, points in layers.items():
        if set(points) != expected:
            raise ManualTrainingError(
                f"Feature '{name}' does not cover the same X/Y grid as the other layers.",
                code="CSV_ALIGNMENT",
            )
    if labels is not None and set(labels) != expected:
        raise ManualTrainingError(
            "Training labels do not cover the same X/Y grid as the features.",
            code="CSV_ALIGNMENT",
        )


def _stack_grids(
    layers: dict[str, dict[tuple[float, float], float]],
    labels: dict[tuple[float, float], int],
    xs: list[float],
    ys: list[float],
) -> tuple[np.ndarray, np.ndarray]:
    height = len(ys)
    width = len(xs)
    y_to_row = {_key(y): index for index, y in enumerate(reversed(ys))}
    x_to_col = {_key(x): index for index, x in enumerate(xs)}
    stack = np.full((CHANNEL_COUNT, height, width), FEATURE_NODATA, dtype=np.float64)
    label_grid = np.full((height, width), LABEL_NODATA, dtype=np.int16)
    for channel_index, name in enumerate(CHANNEL_NAMES):
        for (x, y), value in layers[name].items():
            stack[channel_index, y_to_row[y], x_to_col[x]] = value
    for (x, y), value in labels.items():
        label_grid[y_to_row[y], x_to_col[x]] = value
    if stack.shape[0] != CHANNEL_COUNT:
        raise ManualTrainingError(
            f"Feature stack has {stack.shape[0]} channels; SSRI requires {CHANNEL_COUNT}.",
            code="CSV_CHANNELS",
        )
    return stack, label_grid


def _write_tiles(
    dataset_root: Path,
    *,
    stack: np.ndarray,
    labels: np.ndarray,
    xs: list[float],
    ys: list[float],
    x_spacing: float,
    y_spacing: float,
    crs: str,
) -> DatasetSplit:
    height, width = labels.shape
    windows = _windows(height, width)
    train_ids: list[str] = []
    val_ids: list[str] = []
    north = list(reversed(ys))
    for sample_id, row, col, tile_h, tile_w, split_name in windows:
        feature = stack[:, row : row + tile_h, col : col + tile_w]
        label = labels[row : row + tile_h, col : col + tile_w]
        sample_dir = dataset_root / split_name / sample_id
        sample_dir.mkdir(parents=True, exist_ok=True)
        np.save(sample_dir / "feature_stack.npy", feature)
        origin_x = xs[col] - x_spacing / 2
        origin_y = north[row] + y_spacing / 2
        _write_label(sample_dir / "label.tif", label, crs=crs, origin_x=origin_x, origin_y=origin_y, x_spacing=x_spacing, y_spacing=y_spacing)
        metadata = {
            "sample_id": sample_id,
            "crs": crs,
            "resolution_m": abs(x_spacing),
            "source_format": "csv",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "label_classes": list(label_class_names()),
        }
        (sample_dir / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        (train_ids if split_name == "train" else val_ids).append(sample_id)
    if not train_ids or not val_ids:
        raise ManualTrainingError(
            f"The reconstructed grid is {height}×{width}. "
            "SSRI needs separate train and validation areas, so the grid must be at least 8×16.",
            code="CSV_GRID",
        )
    return DatasetSplit(train=tuple(train_ids), validation=tuple(val_ids), test=())


def _windows(height: int, width: int) -> list[tuple[str, int, int, int, int, str]]:
    if height >= TILE and width >= TILE * 2:
        rows = height // TILE
        cols = width // TILE
        split_col = max(1, int(cols * 0.7))
        if split_col >= cols:
            split_col = cols - 1
        windows = []
        for row in range(rows):
            for col in range(cols):
                split_name = "train" if col < split_col else "validation"
                sample_id = f"r{row:03d}_c{col:03d}"
                windows.append((sample_id, row * TILE, col * TILE, TILE, TILE, split_name))
        return windows
    if height >= MIN_TILE and width >= MIN_TILE * 2:
        half = width // 2
        return [
            ("west", 0, 0, height, half, "train"),
            ("east", 0, half, height, width - half, "validation"),
        ]
    if width >= MIN_TILE and height >= MIN_TILE * 2:
        half = height // 2
        return [
            ("north", 0, 0, half, width, "train"),
            ("south", half, 0, height - half, width, "validation"),
        ]
    return []


def _write_label(
    path: Path,
    label: np.ndarray,
    *,
    crs: str,
    origin_x: float,
    origin_y: float,
    x_spacing: float,
    y_spacing: float,
) -> None:
    profile = {
        "driver": "GTiff",
        "height": int(label.shape[0]),
        "width": int(label.shape[1]),
        "count": 1,
        "dtype": "float32",
        "crs": crs,
        "transform": Affine(x_spacing, 0.0, origin_x, 0.0, -abs(y_spacing), origin_y),
        "nodata": float(LABEL_NODATA),
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(label.astype(np.float32), 1)


def _analysis(
    *,
    kind: str,
    rows: int,
    xs: list[float],
    ys: list[float],
    x_spacing: float,
    y_spacing: float,
    crs: str,
    layers: dict,
    labels: dict | None,
) -> dict:
    return {
        "source_format": "csv",
        "csv_kind": kind,
        "rows": rows,
        "grid": {"width": len(xs), "height": len(ys)},
        "x_spacing": x_spacing,
        "y_spacing": y_spacing,
        "crs": crs,
        "detected_features": [name for name in CHANNEL_NAMES if name in layers] or list(layers),
        "missing_features": [name for name in CHANNEL_NAMES if name not in layers],
        "labels_detected": labels is not None,
        "trainable": False,
        "status": "FAILED",
    }


def _number(raw: str, *, filename: str, row_number: int, column: str) -> float:
    try:
        value = float(raw)
    except ValueError as exc:
        raise ManualTrainingError(
            f"{filename} row {row_number} column {column} is not a number.",
            code="CSV_NUMBER",
        ) from exc
    if not np.isfinite(value):
        raise ManualTrainingError(
            f"{filename} row {row_number} column {column} is not a finite number.",
            code="CSV_NUMBER",
        )
    return value


def _key(value: float) -> float:
    return round(float(value), 8)
