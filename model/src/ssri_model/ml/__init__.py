"""Machine learning foundation for the SSRI model package."""

from ssri_model.ml.collate import ssri_collate_fn
from ssri_model.ml.constants import (
    CHANNEL_COUNT,
    CHANNEL_NAMES,
    DEFAULT_RANDOM_SEED,
    DEFAULT_RESOLUTION,
    DEFAULT_SPLIT,
    FEATURE_NODATA,
    LABEL_NODATA,
    SUPPORTED_LABELS,
)
from ssri_model.ml.dataloader import create_dataloader
from ssri_model.ml.dataset import SSRIDataset
from ssri_model.ml.dataset_spec import DatasetManifest, FeatureSample
from ssri_model.ml.exceptions import (
    BatchShapeError,
    EmptyDatasetError,
    InvalidFeatureTensorError,
    InvalidLabelError,
    MLDatasetError,
    NormalizationError,
    SplitError,
    StatisticsError,
)
from ssri_model.ml.labels import LabelClass, is_supported_label, label_class_names
from ssri_model.ml.metadata import SampleMetadata
from ssri_model.ml.normalization import (
    CHANNEL_NORMALIZATION,
    NormalizationConfig,
    NormalizationMethod,
    normalize_channel_array,
    normalize_feature_stack,
    validate_normalization_config,
)
from ssri_model.ml.splits import DatasetSplit, SplitConfig, split_sample_ids
from ssri_model.ml.statistics_loader import (
    ChannelStatistics,
    FeatureStatistics,
    compute_feature_statistics_from_arrays,
    load_feature_statistics,
)
from ssri_model.ml.transforms import (
    Compose,
    HorizontalFlip,
    Rotate90,
    SpatialTransform,
    VerticalFlip,
)

__all__ = [
    "CHANNEL_COUNT",
    "CHANNEL_NAMES",
    "CHANNEL_NORMALIZATION",
    "DEFAULT_RANDOM_SEED",
    "DEFAULT_RESOLUTION",
    "DEFAULT_SPLIT",
    "FEATURE_NODATA",
    "LABEL_NODATA",
    "SUPPORTED_LABELS",
    "BatchShapeError",
    "ChannelStatistics",
    "Compose",
    "DatasetManifest",
    "DatasetSplit",
    "EmptyDatasetError",
    "FeatureSample",
    "FeatureStatistics",
    "HorizontalFlip",
    "InvalidFeatureTensorError",
    "InvalidLabelError",
    "LabelClass",
    "MLDatasetError",
    "NormalizationConfig",
    "NormalizationError",
    "NormalizationMethod",
    "Rotate90",
    "SSRIDataset",
    "SampleMetadata",
    "SpatialTransform",
    "SplitConfig",
    "SplitError",
    "StatisticsError",
    "VerticalFlip",
    "compute_feature_statistics_from_arrays",
    "create_dataloader",
    "is_supported_label",
    "label_class_names",
    "load_feature_statistics",
    "normalize_channel_array",
    "normalize_feature_stack",
    "split_sample_ids",
    "ssri_collate_fn",
    "validate_normalization_config",
]
