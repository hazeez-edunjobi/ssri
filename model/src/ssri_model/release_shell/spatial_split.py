"""Whole-block spatial splits with optional buffer (release shell).

Default block size remains 5 degrees. Local sites may use smaller blocks
(e.g. 5–20 km) via ``block_size_deg`` / ``block_size_km``.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Any, Sequence

# Approximate metres per degree latitude (used only for km→deg conversion).
_M_PER_DEG_LAT = 111_320.0
DEFAULT_BLOCK_SIZE_DEG = 5.0


def block_size_deg_from_km(size_km: float) -> float:
    if size_km <= 0:
        raise ValueError("block_size_km must be positive.")
    return float(size_km) * 1000.0 / _M_PER_DEG_LAT


def resolve_block_size_deg(
    *,
    block_size_deg: float | None = None,
    block_size_km: float | None = None,
) -> float:
    if block_size_km is not None and block_size_deg is not None:
        raise ValueError("Pass only one of block_size_deg or block_size_km.")
    if block_size_km is not None:
        return block_size_deg_from_km(block_size_km)
    if block_size_deg is not None:
        if block_size_deg <= 0:
            raise ValueError("block_size_deg must be positive.")
        return float(block_size_deg)
    return DEFAULT_BLOCK_SIZE_DEG


def block_id(lat: float, lon: float, *, size_deg: float = DEFAULT_BLOCK_SIZE_DEG) -> str:
    """Stable block id for a lat/lon at the given block size in degrees."""
    s = float(size_deg)
    if s <= 0:
        raise ValueError("size_deg must be positive.")
    return f"{int(math.floor(lat / s) * s)}_{int(math.floor(lon / s) * s)}"


def block5(lat: float, lon: float) -> str:
    """Backward-compatible 5° block id."""
    return block_id(lat, lon, size_deg=DEFAULT_BLOCK_SIZE_DEG)


def is_local_block_size(size_deg: float) -> bool:
    """True when block size is below the historic 5° default."""
    return float(size_deg) < DEFAULT_BLOCK_SIZE_DEG - 1e-12


LOCAL_EVIDENCE_LIMITATION = (
    "local evidence only; not validated beyond this site"
)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmb = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dlmb / 2) ** 2
    return 2 * r * math.asin(min(1.0, math.sqrt(a)))


@dataclass(frozen=True)
class TileGeo:
    sample_id: str
    lat: float
    lon: float
    crs: str | None = None


@dataclass(frozen=True)
class SpatialSplitResult:
    train_ids: tuple[str, ...]
    validation_ids: tuple[str, ...]
    test_ids: tuple[str, ...]
    train_blocks: tuple[str, ...]
    validation_blocks: tuple[str, ...]
    test_blocks: tuple[str, ...]
    buffer_km: float
    policy: str
    dropped_by_buffer: tuple[str, ...]
    block_size_deg: float = DEFAULT_BLOCK_SIZE_DEG
    local_evidence_only: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "train": list(self.train_ids),
            "validation": list(self.validation_ids),
            "test": list(self.test_ids),
            "train_blocks": list(self.train_blocks),
            "validation_blocks": list(self.validation_blocks),
            "test_blocks": list(self.test_blocks),
            "buffer_km": self.buffer_km,
            "policy": self.policy,
            "dropped_by_buffer": list(self.dropped_by_buffer),
            "block_size_deg": self.block_size_deg,
            "local_evidence_only": self.local_evidence_only,
            "limitations": [LOCAL_EVIDENCE_LIMITATION] if self.local_evidence_only else [],
        }


def assert_block_disjoint(
    train_blocks: Sequence[str],
    val_blocks: Sequence[str],
    test_blocks: Sequence[str],
) -> None:
    t, v, te = set(train_blocks), set(val_blocks), set(test_blocks)
    if t & v:
        raise ValueError(f"Train and validation blocks overlap: {sorted(t & v)}")
    if t & te:
        raise ValueError(f"Train and test blocks overlap: {sorted(t & te)}")
    if v & te:
        raise ValueError(f"Validation and test blocks overlap: {sorted(v & te)}")


def split_by_blocks(
    tiles: Sequence[TileGeo],
    *,
    held_out_fraction: float = 0.25,
    val_fraction_of_train_blocks: float = 0.2,
    buffer_km: float = 50.0,
    min_held_out_blocks: int = 3,
    seed: int = 42,
    block_size_deg: float | None = None,
    block_size_km: float | None = None,
) -> SpatialSplitResult:
    """Assign whole blocks to train/val/test; drop train tiles within buffer of holdouts.

    Default block size is 5°. For local AOIs pass ``block_size_km`` (e.g. 10).
    """
    if not tiles:
        raise ValueError(
            "Cannot build a spatial split: no tiles with coordinates were provided."
        )
    size_deg = resolve_block_size_deg(
        block_size_deg=block_size_deg, block_size_km=block_size_km
    )
    local = is_local_block_size(size_deg)
    # CRS required at dataset level — caller should refuse before calling if all missing
    by_block: dict[str, list[TileGeo]] = defaultdict(list)
    for t in tiles:
        by_block[block_id(t.lat, t.lon, size_deg=size_deg)].append(t)

    blocks = sorted(by_block.keys())
    if len(blocks) < max(2, min_held_out_blocks + 1):
        raise ValueError(
            f"Need at least {max(2, min_held_out_blocks + 1)} distinct "
            f"{size_deg:g}° blocks for a spatial split; found {len(blocks)}."
        )

    rng_blocks = list(blocks)
    # Deterministic shuffle
    import random

    rng = random.Random(seed)
    rng.shuffle(rng_blocks)

    n_test = max(min_held_out_blocks, int(round(len(rng_blocks) * held_out_fraction)))
    n_test = min(n_test, len(rng_blocks) - 2)
    test_blocks = tuple(sorted(rng_blocks[:n_test]))
    remain = rng_blocks[n_test:]
    n_val = max(1, int(round(len(remain) * val_fraction_of_train_blocks)))
    n_val = min(n_val, len(remain) - 1)
    validation_blocks = tuple(sorted(remain[:n_val]))
    train_blocks = tuple(sorted(remain[n_val:]))
    assert_block_disjoint(train_blocks, validation_blocks, test_blocks)

    hold_tiles = [
        t for b in list(test_blocks) + list(validation_blocks) for t in by_block[b]
    ]

    def far_enough(t: TileGeo) -> bool:
        if buffer_km <= 0:
            return True
        return all(
            haversine_km(t.lat, t.lon, h.lat, h.lon) >= buffer_km for h in hold_tiles
        )

    train_ids: list[str] = []
    dropped: list[str] = []
    for b in train_blocks:
        for t in by_block[b]:
            if far_enough(t):
                train_ids.append(t.sample_id)
            else:
                dropped.append(t.sample_id)

    val_ids = [t.sample_id for b in validation_blocks for t in by_block[b]]
    test_ids = [t.sample_id for b in test_blocks for t in by_block[b]]

    if not train_ids or not val_ids or not test_ids:
        raise ValueError(
            "Spatial split produced an empty train, validation, or test set after "
            f"applying the {buffer_km} km buffer. Add more geographically spread tiles."
        )

    policy = (
        f"whole_{size_deg:g}deg_blocks_with_buffer"
        if not local
        else f"local_{size_deg:g}deg_blocks_with_buffer"
    )
    return SpatialSplitResult(
        train_ids=tuple(train_ids),
        validation_ids=tuple(val_ids),
        test_ids=tuple(test_ids),
        train_blocks=train_blocks,
        validation_blocks=validation_blocks,
        test_blocks=test_blocks,
        buffer_km=buffer_km,
        policy=policy,
        dropped_by_buffer=tuple(dropped),
        block_size_deg=size_deg,
        local_evidence_only=local,
    )
