"""Configuration for SSRI scientific validation."""

from __future__ import annotations

from dataclasses import dataclass

from ssri_model.ml.constants import DEFAULT_RANDOM_SEED
from ssri_model.scientific.exceptions import InvalidScientificConfigError


@dataclass(frozen=True)
class ScientificValidationConfig:
    """Engineering/data-quality thresholds for scientific validation audits.

    These thresholds are data-quality criteria, not geological truth claims.
    """

    min_samples_per_class: int = 1
    min_valid_pixel_fraction: float = 0.01
    max_nodata_fraction: float = 0.95
    max_train_test_overlap: int = 0
    max_validation_test_overlap: int = 0
    max_feature_label_correlation: float = 0.99
    spatial_buffer_m: float = 0.0
    random_seed: int = DEFAULT_RANDOM_SEED
    min_class_pixel_count: int = 10
    max_class_dominance_fraction: float = 0.99
    distribution_shift_z_threshold: float = 3.0
    constant_channel_std_threshold: float = 1e-12

    def __post_init__(self) -> None:
        if self.min_samples_per_class < 0:
            raise InvalidScientificConfigError("min_samples_per_class must be non-negative")
        if not 0.0 <= self.min_valid_pixel_fraction <= 1.0:
            raise InvalidScientificConfigError(
                "min_valid_pixel_fraction must be between 0 and 1"
            )
        if not 0.0 <= self.max_nodata_fraction <= 1.0:
            raise InvalidScientificConfigError("max_nodata_fraction must be between 0 and 1")
        if self.spatial_buffer_m < 0.0:
            raise InvalidScientificConfigError("spatial_buffer_m must be non-negative")
        if not 0.0 <= self.max_feature_label_correlation <= 1.0:
            raise InvalidScientificConfigError(
                "max_feature_label_correlation must be between 0 and 1"
            )
