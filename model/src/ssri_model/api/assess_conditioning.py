"""Sample conditioning channels from an assessment feature tensor.

Reports lineament and overburden values only when they exist in the tensor.
Never fabricates measurements or substitutes zero for NoData.
"""

from __future__ import annotations

from typing import Any, Sequence

import numpy as np
import torch

from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.release_shell.channel_schema import (
    CHANNEL_NAMES_V2,
    LINEAMENT_DENSITY,
    LINEAMENT_DISTANCE,
    OVERBURDEN_THICKNESS,
)

CONDITIONING_CHANNELS: tuple[str, ...] = (
    OVERBURDEN_THICKNESS,
    LINEAMENT_DENSITY,
    LINEAMENT_DISTANCE,
)

CONDITIONING_UNITS: dict[str, str] = {
    OVERBURDEN_THICKNESS: "m (thickness; not depth-to-interface)",
    LINEAMENT_DENSITY: "derived density (training units)",
    LINEAMENT_DISTANCE: "m (distance to nearest lineament segment)",
}


def resolve_channel_names(channel_count: int, advertised: Sequence[str] | None = None) -> list[str]:
    if advertised and len(advertised) == channel_count:
        return [str(n) for n in advertised]
    if channel_count == len(CHANNEL_NAMES_V2):
        return list(CHANNEL_NAMES_V2)
    if channel_count == CHANNEL_COUNT:
        return list(CHANNEL_NAMES)
    return [f"channel_{i}" for i in range(channel_count)]


def sample_conditioning_features(
    features: torch.Tensor | np.ndarray,
    *,
    channel_names: Sequence[str] | None = None,
    pixel_row: int | None = None,
    pixel_col: int | None = None,
    aoi_source: str | None = None,
) -> dict[str, Any]:
    """Return honesty-preserving conditioning summaries for the assess response."""
    array = features.detach().cpu().numpy() if isinstance(features, torch.Tensor) else np.asarray(features)
    if array.ndim == 4:
        array = array[0]
    if array.ndim != 3:
        raise ValueError(f"features must be (C,H,W) or (B,C,H,W); got shape {array.shape}")

    channel_count, height, width = int(array.shape[0]), int(array.shape[1]), int(array.shape[2])
    names = resolve_channel_names(channel_count, channel_names)
    name_to_index = {name: i for i, name in enumerate(names)}

    if pixel_row is None or pixel_col is None or not (
        0 <= int(pixel_row) < height and 0 <= int(pixel_col) < width
    ):
        row = height // 2
        col = width // 2
        sample_policy = "tensor_centre"
        sample_note = (
            "Query grid cell was unavailable or outside the feature tensor; "
            "sampled the centre cell of the provided stack."
        )
    else:
        row = int(pixel_row)
        col = int(pixel_col)
        sample_policy = "query_grid_cell"
        sample_note = "Sampled the feature tensor at the query grid cell."

    layers: dict[str, Any] = {}
    for name in CONDITIONING_CHANNELS:
        unit = CONDITIONING_UNITS[name]
        if name not in name_to_index:
            layers[name] = {
                "status": "unavailable",
                "value": None,
                "unit": unit,
                "reason": (
                    "Channel not present in this assessment feature stack "
                    f"(schema has {channel_count} channels). Live AOI acquisition "
                    "is Stage 2.5 v1 (13 channels) and does not acquire lineaments "
                    "or overburden. Apply those layers during training/shell dataset "
                    "preparation and assess with a matching schema-v2 offline stack."
                ),
            }
            continue
        index = name_to_index[name]
        raw = float(array[index, row, col])
        if not np.isfinite(raw) or abs(raw - float(FEATURE_NODATA)) < 1e-3:
            layers[name] = {
                "status": "nodata",
                "value": None,
                "unit": unit,
                "reason": (
                    "Cell is NoData or non-finite. Missing coverage is not treated as zero."
                ),
            }
            continue
        layers[name] = {
            "status": "available",
            "value": raw,
            "unit": unit,
            "reason": None,
        }

    return {
        "schema_channel_count": channel_count,
        "channel_names": names,
        "sample_policy": sample_policy,
        "sample_row": row,
        "sample_col": col,
        "aoi_source": aoi_source,
        "notes": [
            sample_note,
            "Overburden values are thickness only when status=available; "
            "depth-to-interface is not auto-converted.",
            "Lineament density/distance are model conditioning features when present "
            "in a schema-v2 stack; they are not independently validated hazard scores.",
        ],
        "layers": layers,
    }
