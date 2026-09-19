"""Dataset specification types for SSRI machine learning."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.ml.labels import label_class_names
from ssri_model.ml.normalization import NormalizationConfig


@dataclass(frozen=True)
class FeatureSample:
    """Reference to one feature/label sample on disk."""

    sample_id: str
    feature_path: Path | str
    label_path: Path | str | None
    metadata_path: Path | str

    def to_dict(self) -> dict[str, Any]:
        """Convert the sample reference to a JSON-serializable dictionary."""
        return {
            "sample_id": self.sample_id,
            "feature_path": str(self.feature_path),
            "label_path": str(self.label_path) if self.label_path is not None else None,
            "metadata_path": str(self.metadata_path),
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> FeatureSample:
        """Build a sample reference from a dictionary."""
        label_path = payload.get("label_path")
        return cls(
            sample_id=str(payload["sample_id"]),
            feature_path=Path(str(payload["feature_path"])),
            label_path=Path(str(label_path)) if label_path is not None else None,
            metadata_path=Path(str(payload["metadata_path"])),
        )


@dataclass(frozen=True)
class DatasetManifest:
    """Versioned dataset manifest for SSRI training consumption."""

    dataset_name: str
    version: str
    created_at: str
    channels: tuple[str, ...]
    label_classes: tuple[str, ...]
    resolution: float
    crs: str
    normalization: dict[str, str]
    train_count: int
    validation_count: int
    test_count: int

    @classmethod
    def create(
        cls,
        *,
        dataset_name: str,
        version: str,
        resolution: float,
        crs: str,
        normalization: NormalizationConfig | None = None,
        train_count: int = 0,
        validation_count: int = 0,
        test_count: int = 0,
        created_at: str | None = None,
    ) -> DatasetManifest:
        """Create a manifest using canonical Stage 1/2 defaults."""
        config = normalization or NormalizationConfig.default()
        return cls(
            dataset_name=dataset_name,
            version=version,
            created_at=created_at or datetime.now(timezone.utc).isoformat(),
            channels=CHANNEL_NAMES,
            label_classes=label_class_names(),
            resolution=resolution,
            crs=crs,
            normalization=config.as_dict(),
            train_count=train_count,
            validation_count=validation_count,
            test_count=test_count,
        )

    def to_dict(self) -> dict[str, Any]:
        """Convert the manifest to a JSON-serializable dictionary."""
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> DatasetManifest:
        """Build a manifest from a dictionary."""
        return cls(
            dataset_name=str(payload["dataset_name"]),
            version=str(payload["version"]),
            created_at=str(payload["created_at"]),
            channels=tuple(payload["channels"]),
            label_classes=tuple(payload["label_classes"]),
            resolution=float(payload["resolution"]),
            crs=str(payload["crs"]),
            normalization=dict(payload["normalization"]),
            train_count=int(payload["train_count"]),
            validation_count=int(payload["validation_count"]),
            test_count=int(payload["test_count"]),
        )

    def save(self, path: Path | str) -> Path:
        """Persist the manifest to a JSON file."""
        destination = Path(path)
        destination.parent.mkdir(parents=True, exist_ok=True)
        with destination.open("w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2)
        return destination

    @classmethod
    def load(cls, path: Path | str) -> DatasetManifest:
        """Load a manifest from a JSON file."""
        with Path(path).open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return cls.from_dict(payload)
