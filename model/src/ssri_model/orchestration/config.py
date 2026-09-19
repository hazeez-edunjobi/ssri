"""Configuration for SSRI batch orchestration."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

from ssri_model.inference.config import InferenceConfig
from ssri_model.orchestration.exceptions import InvalidBatchConfigError, InvalidJobSpecError
from ssri_model.training.config import DeviceType


@dataclass(frozen=True)
class JobSpec:
    """Typed specification for one SSRI inference job."""

    job_id: str
    checkpoint: str
    features: str
    manifest: str
    statistics: str
    output_dir: str = ""
    inference_config: Mapping[str, Any] | None = None
    description: str | None = None
    metadata: Mapping[str, Any] | None = None

    def __post_init__(self) -> None:
        if not self.job_id or not self.job_id.strip():
            raise InvalidJobSpecError("job_id must be non-empty")

    @property
    def checkpoint_path(self) -> Path:
        return Path(self.checkpoint)

    @property
    def features_path(self) -> Path:
        return Path(self.features)

    @property
    def manifest_path(self) -> Path:
        return Path(self.manifest)

    @property
    def statistics_path(self) -> Path:
        return Path(self.statistics)

    @property
    def output_path(self) -> Path:
        return Path(self.output_dir) if self.output_dir else Path()

    def to_inference_config(self, *, output_dir: Path, device: DeviceType) -> InferenceConfig:
        """Build a Stage 2.7 InferenceConfig for this job."""
        overrides = dict(self.inference_config or {})
        device_value = overrides.pop("device", device)
        return InferenceConfig(
            checkpoint_path=str(self.checkpoint_path),
            feature_path=str(self.features_path),
            manifest_path=str(self.manifest_path),
            statistics_path=str(self.statistics_path),
            output_dir=str(output_dir),
            tile_size=int(overrides.pop("tile_size", 512)),
            overlap=int(overrides.pop("overlap", 64)),
            batch_size=int(overrides.pop("batch_size", 4)),
            device=device_value,
            mixed_precision=bool(overrides.pop("mixed_precision", False)),
            save_individual_probability_bands=bool(
                overrides.pop("save_individual_probability_bands", False)
            ),
        )


@dataclass(frozen=True)
class BatchConfig:
    """Configuration for a batch inference run."""

    output_root: str
    max_workers: int = 1
    fail_fast: bool = False
    resume: bool = False
    overwrite: bool = False
    continue_on_error: bool = True
    device: DeviceType = "auto"
    batch_id: str | None = None

    def __post_init__(self) -> None:
        if self.max_workers < 1:
            raise InvalidBatchConfigError("max_workers must be at least 1")
        if self.device not in ("auto", "cpu", "cuda"):
            raise InvalidBatchConfigError(f"Unsupported device: {self.device}")
        if self.overwrite and self.resume:
            raise InvalidBatchConfigError("overwrite and resume cannot both be enabled")

    @property
    def output_root_path(self) -> Path:
        return Path(self.output_root)


@dataclass(frozen=True)
class BatchJobsFile:
    """Parsed jobs.json batch definition."""

    batch_id: str
    jobs: tuple[JobSpec, ...]
    metadata: Mapping[str, Any] = field(default_factory=dict)
