"""Catalogue overlays for live assess: lineament / overburden / magnetic context.

Does **not** inject channels into Stage 2.5 v1 (13-channel) inference tensors.
Activated overburden thickness and lineament vectors may be sampled at the AOI
as analytics. TMI magnetic interpretation themes may be attached as geological
context when the AOI intersects a validated TMI footprint.

Never treats TMI Z as overburden thickness. Never fabricates lineament geometries.
"""

from __future__ import annotations

import csv
import io
import math
from pathlib import Path
from typing import Any, Sequence

from ssri_model.geological.durable import build_geological_storage
from ssri_model.geological.models import (
    MEASUREMENT_LINEAMENT,
    MEASUREMENT_OVERBURDEN_THICKNESS,
    MEASUREMENT_TOTAL_MAGNETIC_INTENSITY,
    canonicalize_measurement_type,
)
from ssri_model.geological.magnetic_processing import publication_comparison_notes
from ssri_model.release_shell.lineaments import (
    DEFAULT_WINDOW_M,
    LineamentMethod,
    _point_segment_distance,
    _segment_length_in_window,
    load_lineament_segments,
)

_ACTIVATED = frozenset({"reporting_only", "approved"})


def _point_in_bbox(
    lon: float, lat: float, bbox: Sequence[float] | None
) -> bool:
    if not bbox or len(bbox) != 4:
        return False
    west, south, east, north = (float(v) for v in bbox)
    return west <= lon <= east and south <= lat <= north


def _display_bbox(record) -> list[float] | None:
    payload = record.to_dict() if hasattr(record, "to_dict") else {}
    box = payload.get("display_bbox_wgs84")
    if isinstance(box, list) and len(box) == 4:
        return [float(v) for v in box]
    prov = record.provenance or {}
    box = prov.get("display_bbox_wgs84")
    if isinstance(box, list) and len(box) == 4:
        return [float(v) for v in box]
    crs = (record.crs or "").upper().replace(" ", "")
    cov = record.coverage_bbox
    if cov and len(cov) == 4 and ("4326" in crs or crs in {"WGS84", "CRS84"}):
        return [float(v) for v in cov]
    return None


def _transform_lonlat_to_crs(
    lon: float, lat: float, crs: str
) -> tuple[float, float] | None:
    try:
        from pyproj import Transformer
    except Exception:
        return None
    try:
        transformer = Transformer.from_crs("EPSG:4326", crs, always_xy=True)
        x, y = transformer.transform(lon, lat)
        if not (math.isfinite(x) and math.isfinite(y)):
            return None
        return float(x), float(y)
    except Exception:
        return None


def _sample_overburden_csv(
    *,
    csv_path: Path,
    x_col: str | int | None,
    y_col: str | int | None,
    z_col: str | int | None,
    target_xy: tuple[float, float],
    max_distance: float,
) -> dict[str, Any]:
    raw = csv_path.read_bytes()
    text = raw.decode("utf-8-sig", errors="replace")
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        return {"status": "nodata", "value": None, "reason": "Overburden CSV is empty."}
    header = rows[0]
    def _idx(col: str | int | None, default: int) -> int:
        if isinstance(col, int):
            return col
        if isinstance(col, str) and col in header:
            return header.index(col)
        return default

    ix, iy, iz = _idx(x_col, 0), _idx(y_col, 1), _idx(z_col, 2)
    tx, ty = target_xy
    best: tuple[float, float] | None = None  # (dist, z)
    for row in rows[1:]:
        if len(row) <= max(ix, iy, iz):
            continue
        try:
            x, y, z = float(row[ix]), float(row[iy]), float(row[iz])
        except ValueError:
            continue
        if not all(math.isfinite(v) for v in (x, y, z)):
            continue
        dist = math.hypot(x - tx, y - ty)
        if best is None or dist < best[0]:
            best = (dist, z)
    if best is None:
        return {
            "status": "nodata",
            "value": None,
            "reason": "No finite overburden samples in the covering dataset.",
        }
    dist, z = best
    if dist > max_distance:
        return {
            "status": "nodata",
            "value": None,
            "reason": (
                f"Nearest overburden sample is {dist:.1f} map units from the AOI "
                f"(limit {max_distance:.1f}); treated as outside valid coverage."
            ),
            "nearest_distance": dist,
        }
    if z < 0:
        return {
            "status": "nodata",
            "value": None,
            "reason": (
                "Nearest overburden sample is negative; thickness must be metres ≥ 0. "
                "Value was not substituted into the assessment."
            ),
            "nearest_distance": dist,
            "rejected_value": z,
        }
    return {
        "status": "available",
        "value": float(z),
        "reason": None,
        "nearest_distance": dist,
    }


def _sample_lineaments_at_point(
    *,
    segments: list[tuple[float, float, float, float]],
    x: float,
    y: float,
    window_m: float = DEFAULT_WINDOW_M,
) -> dict[str, Any]:
    method = LineamentMethod(window_m=window_m)
    if not segments:
        return {
            "density": {
                "status": "nodata",
                "value": None,
                "unit": method.density_units,
                "reason": "Lineament dataset has no LineString segments.",
            },
            "distance": {
                "status": "nodata",
                "value": None,
                "unit": method.distance_units,
                "reason": "Lineament dataset has no LineString segments.",
            },
            "method": method.to_dict(),
        }
    half = window_m / 2.0
    area = window_m * window_m
    xmin, xmax, ymin, ymax = x - half, x + half, y - half, y + half
    length = 0.0
    best = float("inf")
    for x1, y1, x2, y2 in segments:
        length += _segment_length_in_window(x1, y1, x2, y2, xmin, xmax, ymin, ymax)
        best = min(best, _point_segment_distance(x, y, x1, y1, x2, y2))
    density = length / area if area > 0 else None
    distance = best if best < float("inf") else None
    return {
        "density": {
            "status": "available" if density is not None else "nodata",
            "value": density,
            "unit": method.density_units,
            "reason": None if density is not None else "Density could not be computed.",
        },
        "distance": {
            "status": "available" if distance is not None else "nodata",
            "value": distance,
            "unit": method.distance_units,
            "reason": None if distance is not None else "Distance could not be computed.",
        },
        "method": method.to_dict(),
    }


def enrich_conditioning_with_geological_catalogue(
    conditioning: dict[str, Any],
    *,
    output_root: Path | str,
    latitude: float | None,
    longitude: float | None,
) -> dict[str, Any]:
    """Attach catalogue overlays + magnetic geological context; never mutates inference."""
    out = dict(conditioning or {})
    layers = dict(out.get("layers") or {})
    notes = list(out.get("notes") or [])
    overlay: dict[str, Any] = {
        "queried": False,
        "used_in_inference": False,
        "latitude": latitude,
        "longitude": longitude,
        "layers": {},
        "geological_context": [],
        "notes": [
            "Catalogue overlays are analytics only. Stage 2.5 v1 live assess uses "
            "13 channels and does not inject lineament/overburden into the checkpoint.",
            "TMI / magnetic interpretation themes are geological context — not confirmed "
            "faults, fractures, or hazard labels.",
        ],
    }

    if latitude is None or longitude is None:
        overlay["notes"].append(
            "No AOI lat/lon available; catalogue overlays were not queried."
        )
        out["catalogue_overlay"] = overlay
        out["layers"] = layers
        out["notes"] = notes
        return out

    lon = float(longitude)
    lat = float(latitude)
    overlay["queried"] = True

    try:
        storage = build_geological_storage(Path(output_root))
        records, _total = storage.list(limit=200, offset=0)
    except Exception as exc:  # pragma: no cover - defensive
        overlay["notes"].append(f"Geological catalogue unavailable: {exc}")
        out["catalogue_overlay"] = overlay
        out["layers"] = layers
        out["notes"] = notes
        return out

    covering = []
    for rec in records:
        bbox = _display_bbox(rec)
        if _point_in_bbox(lon, lat, bbox):
            covering.append((rec, bbox))

    if not covering:
        overlay["notes"].append(
            "No geological catalogue datasets with a verified WGS84 footprint cover this AOI."
        )

    overburden_hit: dict[str, Any] | None = None
    lineament_hit: dict[str, Any] | None = None
    tmi_contexts: list[dict[str, Any]] = []

    for rec, bbox in covering:
        mt = canonicalize_measurement_type(rec.measurement_type)
        activated = rec.activation_status in _ACTIVATED
        validated = rec.validation_status == "validated"

        # Magnetic / TMI context — validated footprint is enough; do not require activation.
        if mt in {MEASUREMENT_TOTAL_MAGNETIC_INTENSITY, "tmi"} and validated:
            themes = publication_comparison_notes()["published_interpretation_themes"]
            prov = rec.provenance or {}
            tmi_contexts.append(
                {
                    "geo_id": rec.geo_id,
                    "display_name": rec.display_name,
                    "kind": "tmi_magnetic_interpretation",
                    "measurement_type": mt,
                    "crs": rec.crs,
                    "working_crs": rec.working_crs,
                    "display_crs": prov.get("display_crs") or "EPSG:4326",
                    "display_bbox_wgs84": bbox,
                    "scientific_validation_status": rec.scientific_validation_status
                    or "NOT_VALIDATED",
                    "published_interpretation_themes": themes,
                    "structural_orientation_theme": themes[-1] if themes else None,
                    "z_meaning": prov.get("z_meaning") or "total_magnetic_intensity",
                    "not_overburden_thickness": True,
                    "not_confirmed_faults_or_fractures": True,
                    "not_hazard_labels": True,
                    "source": prov.get("publication")
                    or "publication-guided magnetic processing provenance",
                }
            )

        # Overburden: activated + thickness only.
        if (
            mt == MEASUREMENT_OVERBURDEN_THICKNESS
            and activated
            and validated
            and overburden_hit is None
        ):
            working = storage.working_path(rec)
            if working is None or not working.exists():
                continue
            target = _transform_lonlat_to_crs(lon, lat, rec.crs or "EPSG:4326")
            if target is None:
                overburden_hit = {
                    "status": "unavailable",
                    "value": None,
                    "unit": "m (thickness; not depth-to-interface)",
                    "reason": f"Could not transform AOI into dataset CRS {rec.crs}.",
                    "used_in_inference": False,
                    "source_geo_id": rec.geo_id,
                }
            else:
                spacing = float(rec.grid_spacing_x or rec.grid_spacing_y or 100.0)
                sample = _sample_overburden_csv(
                    csv_path=working,
                    x_col=rec.x_column,
                    y_col=rec.y_column,
                    z_col=rec.z_column,
                    target_xy=target,
                    max_distance=max(spacing * 1.5, 50.0),
                )
                overburden_hit = {
                    **sample,
                    "unit": "m (thickness; not depth-to-interface)",
                    "used_in_inference": False,
                    "source_geo_id": rec.geo_id,
                    "source_crs": rec.crs,
                }

        # Lineament vectors: activated + validated.
        if (
            (mt == MEASUREMENT_LINEAMENT or rec.asset_kind == "vector_lineament")
            and activated
            and validated
            and lineament_hit is None
        ):
            working = storage.resolve_under(rec.geo_id, "working/lineaments.geojson")
            if working is None or not working.exists():
                continue
            target = _transform_lonlat_to_crs(lon, lat, rec.crs or "EPSG:4326")
            if target is None:
                lineament_hit = {
                    "density": {
                        "status": "unavailable",
                        "value": None,
                        "reason": f"Could not transform AOI into dataset CRS {rec.crs}.",
                    },
                    "distance": {
                        "status": "unavailable",
                        "value": None,
                        "reason": f"Could not transform AOI into dataset CRS {rec.crs}.",
                    },
                    "used_in_inference": False,
                    "source_geo_id": rec.geo_id,
                }
            else:
                try:
                    segments = load_lineament_segments(working)
                except Exception as exc:
                    lineament_hit = {
                        "density": {
                            "status": "unavailable",
                            "value": None,
                            "reason": f"Lineament parse failed: {exc}",
                        },
                        "distance": {
                            "status": "unavailable",
                            "value": None,
                            "reason": f"Lineament parse failed: {exc}",
                        },
                        "used_in_inference": False,
                        "source_geo_id": rec.geo_id,
                    }
                    continue
                sampled = _sample_lineaments_at_point(
                    segments=segments, x=target[0], y=target[1]
                )
                lineament_hit = {
                    **sampled,
                    "used_in_inference": False,
                    "source_geo_id": rec.geo_id,
                    "source_crs": rec.crs,
                    "not_confirmed_faults_or_fractures": True,
                }

    overlay["geological_context"] = tmi_contexts
    if tmi_contexts:
        notes.append(
            "geological_context=tmi_magnetic_interpretation:"
            + ",".join(c["geo_id"] for c in tmi_contexts)
        )
        notes.append(
            "structural_orientation_theme=Predominantly NE-SW (publication-guided; NOT_VALIDATED)"
        )

    # Merge catalogue samples into overlay layers; only fill stack layers when unavailable.
    stack_ob = layers.get("overburden_thickness") or {}
    if overburden_hit:
        overlay["layers"]["overburden_thickness"] = overburden_hit
        if stack_ob.get("status") == "unavailable":
            layers["overburden_thickness"] = {
                "status": overburden_hit["status"],
                "value": overburden_hit.get("value"),
                "unit": overburden_hit.get("unit"),
                "reason": (
                    overburden_hit.get("reason")
                    or "Sampled from activated geological catalogue overburden_thickness "
                    f"({overburden_hit.get('source_geo_id')}). "
                    "Not injected into the 13-channel Stage 2.5 inference tensor."
                ),
                "used_in_inference": False,
                "source": "geological_catalogue",
            }
            notes.append(
                f"conditioning_overburden_thickness=catalogue:{overburden_hit.get('status')}"
            )
    else:
        # Explicit honesty when covering TMI exists but is not thickness.
        if any(c.get("not_overburden_thickness") for c in tmi_contexts):
            reason = (
                "AOI intersects a Total Magnetic Intensity (TMI) catalogue footprint. "
                "TMI Z is not overburden thickness and was not substituted. "
                "No activated overburden_thickness dataset covers this AOI."
            )
            overlay["layers"]["overburden_thickness"] = {
                "status": "unavailable",
                "value": None,
                "unit": "m (thickness; not depth-to-interface)",
                "reason": reason,
                "used_in_inference": False,
            }
            if stack_ob.get("status") == "unavailable":
                layers["overburden_thickness"] = {
                    **layers.get("overburden_thickness", {}),
                    "reason": reason,
                    "used_in_inference": False,
                }

    if lineament_hit:
        dens = lineament_hit.get("density") or {}
        dist = lineament_hit.get("distance") or {}
        overlay["layers"]["lineament_density"] = {
            **dens,
            "used_in_inference": False,
            "source_geo_id": lineament_hit.get("source_geo_id"),
        }
        overlay["layers"]["lineament_distance"] = {
            **dist,
            "used_in_inference": False,
            "source_geo_id": lineament_hit.get("source_geo_id"),
        }
        for key, sample in (
            ("lineament_density", dens),
            ("lineament_distance", dist),
        ):
            stack_layer = layers.get(key) or {}
            if stack_layer.get("status") == "unavailable" and sample:
                layers[key] = {
                    "status": sample.get("status"),
                    "value": sample.get("value"),
                    "unit": sample.get("unit"),
                    "reason": (
                        sample.get("reason")
                        or f"Sampled from activated geological catalogue lineaments "
                        f"({lineament_hit.get('source_geo_id')}). "
                        "Not confirmed faults; not injected into 13-channel inference."
                    ),
                    "used_in_inference": False,
                    "source": "geological_catalogue",
                }
                notes.append(f"conditioning_{key}=catalogue:{sample.get('status')}")
    else:
        reason = (
            "No activated lineament vector dataset covers this AOI. "
            "Magnetic NE–SW structural themes (when present) are geological context only "
            "and are not converted into fabricated lineament geometries."
        )
        overlay["layers"].setdefault(
            "lineament_density",
            {
                "status": "unavailable",
                "value": None,
                "reason": reason,
                "used_in_inference": False,
            },
        )
        overlay["layers"].setdefault(
            "lineament_distance",
            {
                "status": "unavailable",
                "value": None,
                "reason": reason,
                "used_in_inference": False,
            },
        )
        for key in ("lineament_density", "lineament_distance"):
            stack_layer = layers.get(key) or {}
            if stack_layer.get("status") == "unavailable":
                # Prefer catalogue honesty over the generic 13-channel stack message
                # so operators see that magnetic themes were not fabricated into vectors.
                layers[key] = {
                    **stack_layer,
                    "reason": reason,
                    "used_in_inference": False,
                }

    out["layers"] = layers
    out["notes"] = notes
    out["catalogue_overlay"] = overlay
    out["geological_context"] = tmi_contexts
    return out
