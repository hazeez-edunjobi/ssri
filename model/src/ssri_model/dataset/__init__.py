"""SSRI dataset generation pipeline."""

from ssri_model.dataset.builder import (
    DatasetBuildConfig,
    DatasetBuilder,
    DatasetBuildResult,
)
from ssri_model.dataset.catalog import (
    ML_CONTRACT_VERSION,
    STAGE1_VERSION,
    DatasetStatistics,
    load_catalog_manifest,
    write_manifest,
    write_statistics,
)
from ssri_model.dataset.exceptions import (
    ChannelCountError,
    CorruptFileError,
    CRSError,
    DatasetBuildError,
    DatasetError,
    DatasetValidationError,
    LabelDimensionError,
    MetadataIncompleteError,
    MissingValueError,
    TensorShapeError,
)
from ssri_model.dataset.exporter import export_sample
from ssri_model.dataset.labels import (
    LabelNotFoundError,
    LabelProvider,
    LabelProviderError,
    LocalRasterLabelProvider,
    PolygonLabelProvider,
    RemoteLabelProvider,
    require_label,
)
from ssri_model.dataset.sample import build_sample_metadata, feature_sample_from_paths
from ssri_model.dataset.tiling import TileSpec, TilingConfig, tile_aoi, tile_aois
from ssri_model.dataset.validator import validate_dataset_root, validate_sample_directory

__all__ = [
    "ML_CONTRACT_VERSION",
    "STAGE1_VERSION",
    "ChannelCountError",
    "CorruptFileError",
    "CRSError",
    "DatasetBuildConfig",
    "DatasetBuildError",
    "DatasetBuildResult",
    "DatasetBuilder",
    "DatasetError",
    "DatasetStatistics",
    "DatasetValidationError",
    "LabelDimensionError",
    "LabelNotFoundError",
    "LabelProvider",
    "LabelProviderError",
    "LocalRasterLabelProvider",
    "MetadataIncompleteError",
    "MissingValueError",
    "PolygonLabelProvider",
    "RemoteLabelProvider",
    "TensorShapeError",
    "TileSpec",
    "TilingConfig",
    "build_sample_metadata",
    "export_sample",
    "feature_sample_from_paths",
    "load_catalog_manifest",
    "require_label",
    "tile_aoi",
    "tile_aois",
    "validate_dataset_root",
    "validate_sample_directory",
    "write_manifest",
    "write_statistics",
]
