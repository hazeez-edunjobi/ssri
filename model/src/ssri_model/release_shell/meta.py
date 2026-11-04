"""Release-shell metadata stored beside / inside checkpoints."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import torch

META_KEY = "release_shell"
SIDECAR_NAME = "release_shell_meta.json"


def build_training_region(
    tiles: list[dict[str, Any]],
) -> dict[str, Any]:
    """tiles: list of {lat, lon, block}."""
    if not tiles:
        return {"blocks": [], "extent": None}
    lats = [float(t["lat"]) for t in tiles]
    lons = [float(t["lon"]) for t in tiles]
    blocks = sorted({str(t["block"]) for t in tiles})
    return {
        "blocks": blocks,
        "extent": {
            "lat_min": min(lats),
            "lat_max": max(lats),
            "lon_min": min(lons),
            "lon_max": max(lons),
        },
        "n_tiles": len(tiles),
    }


def point_in_training_region(
    lat: float,
    lon: float,
    region: dict[str, Any] | None,
    *,
    pad_deg: float = 0.5,
) -> bool:
    """True if point falls inside stored extent (with small pad) or known blocks."""
    if not region:
        return True
    extent = region.get("extent")
    if extent:
        return (
            float(extent["lat_min"]) - pad_deg <= lat <= float(extent["lat_max"]) + pad_deg
            and float(extent["lon_min"]) - pad_deg
            <= lon
            <= float(extent["lon_max"]) + pad_deg
        )
    return True


def write_sidecar(checkpoint_path: Path | str, meta: dict[str, Any]) -> Path:
    path = Path(checkpoint_path).resolve().parent / SIDECAR_NAME
    path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path


def embed_in_checkpoint(checkpoint_path: Path | str, meta: dict[str, Any]) -> None:
    """Add/replace release_shell key in an existing .pt checkpoint."""
    path = Path(checkpoint_path)
    payload = torch.load(path, map_location="cpu", weights_only=False)
    if not isinstance(payload, dict):
        raise TypeError("Checkpoint payload must be a dict")
    payload[META_KEY] = meta
    torch.save(payload, path)
    write_sidecar(path, meta)


def load_shell_meta(checkpoint_path: Path | str) -> dict[str, Any] | None:
    path = Path(checkpoint_path)
    sidecar = path.resolve().parent / SIDECAR_NAME
    if sidecar.exists():
        return json.loads(sidecar.read_text(encoding="utf-8"))
    try:
        payload = torch.load(path, map_location="cpu", weights_only=False)
    except Exception:  # noqa: BLE001
        return None
    if isinstance(payload, dict) and isinstance(payload.get(META_KEY), dict):
        return dict(payload[META_KEY])
    return None
