"""Versioned channel schemas for release-shell datasets and checkpoints.

v1 is the historical 13-channel Stage 2.5 contract (unchanged).
v2 adds overburden_thickness, lineament_density, and lineament_distance.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from ssri_model.ml.constants import CHANNEL_NAMES as V1_CHANNEL_NAMES

SCHEMA_V1 = "v1"
SCHEMA_V2 = "v2"

# Never silently alias depth_to_bedrock → overburden_thickness.
DEPTH_TO_BEDROCK = "depth_to_bedrock"
OVERBURDEN_THICKNESS = "overburden_thickness"
LINEAMENT_DENSITY = "lineament_density"
LINEAMENT_DISTANCE = "lineament_distance"

V2_EXTRA: tuple[str, ...] = (
    OVERBURDEN_THICKNESS,
    LINEAMENT_DENSITY,
    LINEAMENT_DISTANCE,
)

CHANNEL_NAMES_V1: tuple[str, ...] = tuple(V1_CHANNEL_NAMES)
CHANNEL_NAMES_V2: tuple[str, ...] = CHANNEL_NAMES_V1 + V2_EXTRA

# Declared layer names that are recognized but not part of a schema until mapped.
KNOWN_LAYER_ALIASES: dict[str, str] = {
    "overburden": OVERBURDEN_THICKNESS,
    "overburden_thickness": OVERBURDEN_THICKNESS,
    "thickness": OVERBURDEN_THICKNESS,
    "depth_to_bedrock": DEPTH_TO_BEDROCK,
    "bedrock_depth": DEPTH_TO_BEDROCK,
    "lineament_density": LINEAMENT_DENSITY,
    "lineament_distance": LINEAMENT_DISTANCE,
    "distance_to_lineament": LINEAMENT_DISTANCE,
}


@dataclass(frozen=True)
class ChannelSchema:
    version: str
    channel_names: tuple[str, ...]

    @property
    def channel_count(self) -> int:
        return len(self.channel_names)

    def index_of(self, name: str) -> int:
        return self.channel_names.index(name)

    def to_dict(self) -> dict:
        return {
            "version": self.version,
            "channel_names": list(self.channel_names),
            "channel_count": self.channel_count,
        }


def schema_for_version(version: str) -> ChannelSchema:
    key = (version or SCHEMA_V1).strip().lower()
    if key in {"v1", "1", "stage25", "stage_2_5"}:
        return ChannelSchema(SCHEMA_V1, CHANNEL_NAMES_V1)
    if key in {"v2", "2"}:
        return ChannelSchema(SCHEMA_V2, CHANNEL_NAMES_V2)
    raise ValueError(
        f"Unknown channel schema version '{version}'. Supported: v1, v2."
    )


def default_schema() -> ChannelSchema:
    """Flag-off / classic default remains v1."""
    return schema_for_version(SCHEMA_V1)


def normalize_layer_name(name: str) -> str:
    key = (name or "").strip().lower().replace(" ", "_").replace("-", "_")
    return KNOWN_LAYER_ALIASES.get(key, key)


def assert_channels_match(
    expected: Sequence[str],
    actual: Sequence[str],
    *,
    context: str = "input",
) -> None:
    exp = list(expected)
    act = list(actual)
    if exp == act:
        return
    missing = [n for n in exp if n not in act]
    extra = [n for n in act if n not in exp]
    order_mismatch = exp != act and not missing and not extra
    parts = [f"Channel schema mismatch for {context}."]
    if missing:
        parts.append("Missing channels: " + ", ".join(missing) + ".")
    if extra:
        parts.append("Unexpected channels: " + ", ".join(extra) + ".")
    if order_mismatch:
        parts.append(
            "Channel order differs. Expected: "
            + ", ".join(exp)
            + ". Received: "
            + ", ".join(act)
            + "."
        )
    raise ValueError(" ".join(parts))


def schema_from_checkpoint_payload(payload: dict) -> ChannelSchema:
    """Read schema from checkpoint dict; default v1 for legacy checkpoints."""
    cfg = payload.get("model_config") or {}
    meta = payload.get("release_shell") or payload.get("shell_meta") or {}
    version = (
        meta.get("channel_schema_version")
        or cfg.get("channel_schema_version")
        or payload.get("channel_schema_version")
        or SCHEMA_V1
    )
    names = meta.get("channel_names") or cfg.get("channel_names")
    if names:
        return ChannelSchema(str(version), tuple(str(n) for n in names))
    return schema_for_version(str(version))
