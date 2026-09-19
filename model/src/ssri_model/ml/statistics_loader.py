"""Typed loaders for Stage 2.1 statistics.json used during training prep."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, FEATURE_NODATA
from ssri_model.ml.exceptions import StatisticsError


@dataclass(frozen=True)
class ChannelStatistics:
    """Per-channel summary statistics for normalization."""

    min: float
    max: float
    mean: float
    std: float
    valid_count: int
    nodata_count: int

    def __post_init__(self) -> None:
        for name, value in (
            ("min", self.min),
            ("max", self.max),
            ("mean", self.mean),
            ("std", self.std),
        ):
            if not math.isfinite(value):
                raise StatisticsError(
                    f"Channel statistics field '{name}' must be finite, received {value}"
                )
        if self.valid_count < 0 or self.nodata_count < 0:
            raise StatisticsError("valid_count and nodata_count must be non-negative")


@dataclass(frozen=True)
class FeatureStatistics:
    """Normalization statistics for all canonical SSRI channels."""

    channel_names: tuple[str, ...]
    channels: dict[str, ChannelStatistics]

    @property
    def channel_count(self) -> int:
        return len(self.channel_names)

    def for_channel(self, name: str) -> ChannelStatistics:
        if name not in self.channels:
            raise StatisticsError(f"Missing statistics for channel '{name}'")
        return self.channels[name]


def _parse_channel_stats(name: str, payload: Mapping[str, Any]) -> ChannelStatistics:
    required = ("min", "max", "mean", "std")
    missing = [field for field in required if field not in payload]
    if missing:
        raise StatisticsError(
            f"Channel '{name}' statistics missing fields: {', '.join(missing)}"
        )

    valid_count = int(payload.get("valid_count", 0))
    nodata_count = int(payload.get("nodata_count", 0))
    if "valid_count" not in payload and "nodata_count" not in payload:
        raise StatisticsError(
            f"Channel '{name}' statistics must include valid_count and nodata_count"
        )

    return ChannelStatistics(
        min=float(payload["min"]),
        max=float(payload["max"]),
        mean=float(payload["mean"]),
        std=float(payload["std"]),
        valid_count=valid_count,
        nodata_count=nodata_count,
    )


def load_feature_statistics(path: Path | str) -> FeatureStatistics:
    """Load and validate ``statistics.json`` for normalization."""
    statistics_path = Path(path)
    if not statistics_path.exists():
        raise StatisticsError(f"Statistics file not found: {statistics_path}")

    try:
        payload = json.loads(statistics_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise StatisticsError(
            f"Unable to read statistics file: {statistics_path}"
        ) from exc

    raw_stats = payload.get("channel_stats")
    if not isinstance(raw_stats, Mapping):
        raise StatisticsError("statistics.json must contain a 'channel_stats' object")

    missing_channels = [name for name in CHANNEL_NAMES if name not in raw_stats]
    if missing_channels:
        raise StatisticsError(
            "Statistics missing channels: " + ", ".join(missing_channels)
        )

    extra_channels = [name for name in raw_stats if name not in CHANNEL_NAMES]
    if extra_channels:
        raise StatisticsError(
            "Statistics contain unknown channels: " + ", ".join(extra_channels)
        )

    channels: dict[str, ChannelStatistics] = {}
    for name in CHANNEL_NAMES:
        try:
            channels[name] = _parse_channel_stats(name, raw_stats[name])
        except (TypeError, ValueError) as exc:
            raise StatisticsError(
                f"Invalid statistics payload for channel '{name}'"
            ) from exc

    if len(channels) != CHANNEL_COUNT:
        raise StatisticsError(
            f"Expected statistics for {CHANNEL_COUNT} channels, received {len(channels)}"
        )

    return FeatureStatistics(channel_names=CHANNEL_NAMES, channels=channels)


def compute_feature_statistics_from_arrays(
    tensors: list[Any],
    *,
    nodata: float = FEATURE_NODATA,
) -> FeatureStatistics:
    """Compute feature statistics from in-memory tensors for tests."""
    import numpy as np

    if not tensors:
        raise StatisticsError("Cannot compute statistics from an empty tensor list")

    array = np.stack(tensors, axis=0)
    channels: dict[str, ChannelStatistics] = {}
    for index, name in enumerate(CHANNEL_NAMES):
        channel = array[:, index, :, :]
        valid = channel[channel != nodata]
        if valid.size == 0:
            raise StatisticsError(
                f"Channel '{name}' contains no valid pixels for statistics"
            )
        channels[name] = ChannelStatistics(
            min=float(np.min(valid)),
            max=float(np.max(valid)),
            mean=float(np.mean(valid)),
            std=float(np.std(valid)),
            valid_count=int(valid.size),
            nodata_count=int(channel.size - valid.size),
        )

    return FeatureStatistics(channel_names=CHANNEL_NAMES, channels=channels)
