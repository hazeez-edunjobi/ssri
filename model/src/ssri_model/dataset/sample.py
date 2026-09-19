"""Sample construction helpers for SSRI datasets."""

from __future__ import annotations

from typing import Any, Mapping

from ssri_model import __version__
from ssri_model.data.feature_engineering import DateInput, FeatureStack
from ssri_model.ml.dataset_spec import FeatureSample
from ssri_model.ml.metadata import SampleMetadata

from ssri_model.dataset.tiling import TileSpec


def build_sample_metadata(
    *,
    sample_id: str,
    tile: TileSpec,
    stack: FeatureStack,
    start_date: DateInput,
    end_date: DateInput,
    created_at: str | None = None,
) -> SampleMetadata:
    """Build Stage 2 sample metadata from a Stage 1 feature stack."""
    min_lon, min_lat, max_lon, max_lat = tile.aoi
    manifest = dict(stack.manifest)
    sources = _extract_sources(stack.metadata, manifest)

    return SampleMetadata(
        sample_id=sample_id,
        aoi={
            "bbox_wgs84": {
                "min_lon": min_lon,
                "min_lat": min_lat,
                "max_lon": max_lon,
                "max_lat": max_lat,
            },
            "tile_row": tile.row,
            "tile_col": tile.col,
            "aoi_index": tile.aoi_index,
        },
        acquisition={
            "start_date": str(start_date),
            "end_date": str(end_date),
        },
        resolution_m=float(stack.metadata.get("resolution_m", stack.grid_spec.resolution[0])),
        crs=str(stack.grid_spec.crs),
        sources=sources,
        package_version=__version__,
        created_at=created_at or str(manifest.get("created_at", "")),
    )


def _extract_sources(
    metadata: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> dict[str, str]:
    """Merge source provenance from Stage 1 metadata and manifest."""
    sources: dict[str, str] = {}

    for key in ("dem", "sentinel", "gravity_provider", "magnetic_provider"):
        if key in metadata:
            sources[key] = str(metadata[key])

    manifest_sources = manifest.get("sources")
    if isinstance(manifest_sources, Mapping):
        for key, value in manifest_sources.items():
            sources[str(key)] = str(value)

    if not sources:
        sources["feature_stack"] = "stage1"

    return sources


def feature_sample_from_paths(
    *,
    sample_id: str,
    sample_dir: str | Any,
    has_label: bool,
) -> FeatureSample:
    """Create a ``FeatureSample`` reference from an on-disk sample directory."""
    from pathlib import Path

    directory = Path(sample_dir)
    return FeatureSample(
        sample_id=sample_id,
        feature_path=directory / "feature_stack.npy",
        label_path=(directory / "label.tif") if has_label else None,
        metadata_path=directory / "metadata.json",
    )
