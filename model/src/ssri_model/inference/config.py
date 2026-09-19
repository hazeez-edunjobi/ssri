"""Configuration for SSRI offline inference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from ssri_model.inference.exceptions import InvalidInferenceConfigError
from ssri_model.training.config import DeviceType


@dataclass(frozen=True)
class InferenceConfig:
    """Typed configuration for SSRI geospatial inference."""

    checkpoint_path: str
    feature_path: str
    manifest_path: str
    statistics_path: str
    output_dir: str

    tile_size: int = 512
    overlap: int = 64
    batch_size: int = 4
    device: DeviceType = "auto"
    mixed_precision: bool = False
    save_individual_probability_bands: bool = False

    def __post_init__(self) -> None:
        if self.tile_size <= 0:
            raise InvalidInferenceConfigError("tile_size must be greater than zero")
        if self.overlap < 0:
            raise InvalidInferenceConfigError("overlap must be non-negative")
        if self.overlap >= self.tile_size:
            raise InvalidInferenceConfigError("overlap must be less than tile_size")
        if self.batch_size <= 0:
            raise InvalidInferenceConfigError("batch_size must be greater than zero")
        if self.device not in ("auto", "cpu", "cuda"):
            raise InvalidInferenceConfigError(f"Unsupported device: {self.device}")
        if self.mixed_precision and self.device == "cpu":
            raise InvalidInferenceConfigError(
                "mixed_precision cannot be enabled when device is cpu"
            )

    @property
    def checkpoint(self) -> Path:
        return Path(self.checkpoint_path)

    @property
    def features(self) -> Path:
        return Path(self.feature_path)

    @property
    def manifest(self) -> Path:
        return Path(self.manifest_path)

    @property
    def statistics(self) -> Path:
        return Path(self.statistics_path)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir)
