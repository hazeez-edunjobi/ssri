"""Dataset builder orchestrating Stage 1 and Stage 2 contracts."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Sequence


from ssri_model.data.feature_engineering import (
    AOI,
    BoundingBox,
    DateInput,
    FeatureStack,
    build_feature_stack,
)
from ssri_model.ml.dataset_spec import FeatureSample
from ssri_model.ml.splits import DatasetSplit, SplitConfig, split_sample_ids
from ssri_model.dataset.catalog import write_manifest, write_statistics
from ssri_model.dataset.exceptions import DatasetBuildError
from ssri_model.dataset.exporter import export_sample
from ssri_model.dataset.labels import LabelProvider
from ssri_model.dataset.sample import build_sample_metadata
from ssri_model.dataset.tiling import TileSpec, TilingConfig, tile_aois
from ssri_model.dataset.validator import validate_sample_directory

logger = logging.getLogger(__name__)

FeatureStackBuilder = Callable[..., FeatureStack]


@dataclass
class DatasetBuildConfig:
    """Configuration for dataset generation."""

    dataset_name: str
    version: str
    output_dir: Path | str
    resolution_m: float = 30.0
    tiling: TilingConfig | None = None
    split_config: SplitConfig | None = None
    label_provider: LabelProvider | None = None
    created_at: str | None = None


@dataclass
class DatasetBuildResult:
    """Summary of a completed dataset build."""

    dataset_root: Path
    samples: list[FeatureSample]
    split: DatasetSplit
    manifest_path: Path
    statistics_path: Path


class DatasetBuilder:
    """Convert AOIs into versioned SSRI machine learning datasets."""

    def __init__(
        self,
        config: DatasetBuildConfig,
        *,
        feature_stack_builder: FeatureStackBuilder | None = None,
    ) -> None:
        self.config = config
        self._build_feature_stack = feature_stack_builder or build_feature_stack

    @property
    def dataset_root(self) -> Path:
        """Return the root directory for the generated dataset."""
        return Path(self.config.output_dir) / self.config.dataset_name / self.config.version

    def build(
        self,
        aois: Sequence[AOI],
        start_date: DateInput,
        end_date: DateInput,
    ) -> DatasetBuildResult:
        """Build a dataset from one or more AOIs."""
        if not aois:
            raise DatasetBuildError("At least one AOI is required")

        created_at = self.config.created_at or datetime.now(timezone.utc).isoformat()
        tiles = self._resolve_tiles(aois)
        staging_root = self.dataset_root / "_staging"
        if staging_root.exists():
            shutil.rmtree(staging_root)
        staging_root.mkdir(parents=True, exist_ok=True)

        samples: list[FeatureSample] = []
        reference_crs: str | None = None

        for tile in tiles:
            logger.info("Building feature stack for tile %s", tile.tile_id)
            stack = self._build_feature_stack(
                tile.aoi,
                start_date,
                end_date,
                resolution_m=self.config.resolution_m,
            )
            reference_crs = reference_crs or str(stack.grid_spec.crs)

            label = None
            if self.config.label_provider is not None:
                label = self.config.label_provider.load_label(
                    tile.tile_id,
                    stack.grid_spec,
                )

            metadata = build_sample_metadata(
                sample_id=tile.tile_id,
                tile=tile,
                stack=stack,
                start_date=start_date,
                end_date=end_date,
                created_at=created_at,
            )

            sample_dir = staging_root / tile.tile_id
            sample = export_sample(
                sample_dir,
                stack=stack,
                metadata=metadata,
                label=label,
            )
            validate_sample_directory(sample_dir)
            samples.append(sample)

        split = split_sample_ids(
            [sample.sample_id for sample in samples],
            self.config.split_config,
        )
        self._materialize_splits(staging_root, split)

        manifest_path = write_manifest(
            self.dataset_root,
            dataset_name=self.config.dataset_name,
            version=self.config.version,
            split=split,
            crs=reference_crs or "UNKNOWN",
            resolution_m=self.config.resolution_m,
            created_at=created_at,
        )
        statistics_path = write_statistics(
            self.dataset_root,
            split=split,
            created_at=created_at,
        )

        if staging_root.exists():
            shutil.rmtree(staging_root)

        return DatasetBuildResult(
            dataset_root=self.dataset_root,
            samples=samples,
            split=split,
            manifest_path=manifest_path,
            statistics_path=statistics_path,
        )

    def _resolve_tiles(self, aois: Sequence[AOI]) -> list[TileSpec]:
        bounding_boxes: list[BoundingBox] = []
        for aoi in aois:
            if isinstance(aoi, tuple):
                bounding_boxes.append(aoi)
            else:
                raise DatasetBuildError(
                    "DatasetBuilder currently requires WGS84 bounding box AOIs"
                )

        if self.config.tiling is None:
            return [
                TileSpec(
                    tile_id=f"tile-a{index:03d}-r0000-c0000",
                    aoi=bbox,
                    row=0,
                    col=0,
                    aoi_index=index,
                )
                for index, bbox in enumerate(bounding_boxes)
            ]

        return tile_aois(
            bounding_boxes,
            self.config.tiling,
            resolution_m=self.config.resolution_m,
        )

    def _materialize_splits(
        self,
        staging_root: Path,
        split: DatasetSplit,
    ) -> None:
        mapping = {
            "train": split.train,
            "validation": split.validation,
            "test": split.test,
        }

        for split_name, sample_ids in mapping.items():
            destination_root = self.dataset_root / split_name
            destination_root.mkdir(parents=True, exist_ok=True)
            for sample_id in sample_ids:
                source = staging_root / sample_id
                destination = destination_root / sample_id
                if destination.exists():
                    shutil.rmtree(destination)
                shutil.move(str(source), str(destination))
