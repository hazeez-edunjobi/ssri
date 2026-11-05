"""Spatial block split disjointness and CRS/coordinate refusal."""

from __future__ import annotations

import pytest

from ssri_model.release_shell.spatial_split import (
    TileGeo,
    assert_block_disjoint,
    split_by_blocks,
)


def test_assert_block_disjoint_raises_on_overlap():
    with pytest.raises(ValueError, match="overlap"):
        assert_block_disjoint(["30_-120"], ["30_-120"], ["35_-115"])


def test_split_by_blocks_disjoint_and_nonempty():
    tiles = []
    # 9 blocks
    coords = [
        (32.1, -117.2),
        (37.1, -122.2),
        (42.1, -122.2),
        (47.1, -122.2),
        (32.1, -110.2),
        (37.1, -110.2),
        (42.1, -105.2),
        (35.1, -95.2),
        (40.1, -85.2),
    ]
    for i, (lat, lon) in enumerate(coords):
        tiles.append(TileGeo(f"t{i}", lat, lon, crs="EPSG:4326"))
    result = split_by_blocks(tiles, buffer_km=0.0, min_held_out_blocks=3, seed=0)
    assert_block_disjoint(result.train_blocks, result.validation_blocks, result.test_blocks)
    assert result.train_ids and result.validation_ids and result.test_ids
    assert result.policy == "whole_5deg_blocks_with_buffer"


def test_split_refuses_empty_tiles():
    with pytest.raises(ValueError, match="no tiles"):
        split_by_blocks([])
