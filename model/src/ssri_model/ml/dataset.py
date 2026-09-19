"""PyTorch Dataset for Stage 2.1 SSRI datasets."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

import numpy as np
import rasterio
import torch
from torch.utils.data import Dataset

from ssri_model.ml.constants import (
    CHANNEL_COUNT,
    FEATURE_NODATA,
    LABEL_NODATA,
)
from ssri_model.ml.dataset_spec import DatasetManifest
from ssri_model.ml.exceptions import (
    EmptyDatasetError,
    InvalidFeatureTensorError,
    InvalidLabelError,
    SplitError,
)
from ssri_model.ml.metadata import SampleMetadata
from ssri_model.ml.normalization import NormalizationConfig, normalize_feature_stack
from ssri_model.ml.splits import SplitName
from ssri_model.ml.statistics_loader import FeatureStatistics, load_feature_statistics
from ssri_model.ml.transforms import SpatialTransform


@dataclass(frozen=True)
class SampleIndexEntry:
    """Resolved on-disk location for one dataset sample."""

    sample_id: str
    sample_dir: Path


class SSRIDataset(Dataset):
    """Load normalized SSRI feature/label samples for PyTorch training."""

    def __init__(
        self,
        dataset_root: Path | str,
        split: SplitName,
        *,
        statistics: FeatureStatistics | None = None,
        statistics_path: Path | str | None = None,
        normalization: NormalizationConfig | None = None,
        transform: SpatialTransform | None = None,
        include_metadata: bool = False,
        mmap_features: bool = True,
        feature_nodata: float = FEATURE_NODATA,
        label_nodata: int = LABEL_NODATA,
    ) -> None:
        self.dataset_root = Path(dataset_root)
        self.split = split
        self.transform = transform
        self.include_metadata = include_metadata
        self.mmap_features = mmap_features
        self.feature_nodata = feature_nodata
        self.label_nodata = label_nodata

        self.manifest = self._load_manifest()
        self.normalization = normalization or NormalizationConfig.from_dict(
            self.manifest.normalization
        )
        self.statistics = statistics or load_feature_statistics(
            statistics_path or self.dataset_root / "statistics.json"
        )
        self.label_class_to_index = {
            name: index for index, name in enumerate(self.manifest.label_classes)
        }
        self.index = self._build_index()
        self._validate_split_isolation()

    def _load_manifest(self) -> DatasetManifest:
        manifest_path = self.dataset_root / "manifest.json"
        if not manifest_path.exists():
            raise SplitError(f"Dataset manifest not found: {manifest_path}")
        with manifest_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        return DatasetManifest.from_dict(payload)

    def _build_index(self) -> list[SampleIndexEntry]:
        split_ids = self._split_sample_ids()
        split_dir = self.dataset_root / self.split
        if not split_dir.exists():
            if split_ids:
                raise SplitError(
                    f"Split directory missing for '{self.split}': {split_dir}"
                )
            return []

        entries: list[SampleIndexEntry] = []
        for sample_id in split_ids:
            sample_dir = split_dir / sample_id
            if not sample_dir.exists():
                raise SplitError(
                    f"Sample '{sample_id}' listed in split '{self.split}' "
                    f"but directory not found: {sample_dir}"
                )
            entries.append(SampleIndexEntry(sample_id=sample_id, sample_dir=sample_dir))
        return entries

    def _split_sample_ids(self) -> tuple[str, ...]:
        manifest_path = self.dataset_root / "manifest.json"
        with manifest_path.open(encoding="utf-8") as handle:
            payload = json.load(handle)
        splits = payload.get("splits")
        if not isinstance(splits, Mapping) or self.split not in splits:
            raise SplitError(
                f"Manifest does not define split assignments for '{self.split}'"
            )
        return tuple(str(sample_id) for sample_id in splits[self.split])

    def _validate_split_isolation(self) -> None:
        with (self.dataset_root / "manifest.json").open(encoding="utf-8") as handle:
            payload = json.load(handle)
        splits = payload.get("splits", {})
        allowed = set(splits.get(self.split, []))
        found = {entry.sample_id for entry in self.index}
        if found - allowed:
            raise SplitError(
                f"Dataset index contains samples outside split '{self.split}': "
                f"{sorted(found - allowed)}"
            )

    def __len__(self) -> int:
        return len(self.index)

    def __getitem__(self, index: int) -> dict[str, Any]:
        if len(self.index) == 0:
            raise EmptyDatasetError(
                f"Cannot fetch item from empty '{self.split}' dataset"
            )

        entry = self.index[index]
        features = self._load_features(entry.sample_dir)
        label = self._load_label(entry.sample_dir)
        valid_mask = self._build_valid_mask(features)

        normalized = normalize_feature_stack(
            features,
            valid_mask=valid_mask,
            statistics=self.statistics,
            config=self.normalization,
        )

        sample = {
            "features": torch.from_numpy(normalized),
            "label": torch.from_numpy(label.astype(np.int64)),
            "mask": torch.from_numpy(valid_mask.astype(np.bool_)),
            "sample_id": entry.sample_id,
        }

        if self.include_metadata:
            sample["metadata"] = SampleMetadata.load(entry.sample_dir / "metadata.json")

        if self.transform is not None:
            sample = self.transform(sample)

        return sample

    def _load_features(self, sample_dir: Path) -> np.ndarray:
        feature_path = sample_dir / "feature_stack.npy"
        if not feature_path.exists():
            raise InvalidFeatureTensorError(
                f"Missing feature stack for sample: {feature_path}"
            )

        mmap_mode = "r" if self.mmap_features else None
        try:
            tensor = np.load(feature_path, mmap_mode=mmap_mode)
            array = np.array(tensor, dtype=np.float64)
        except OSError as exc:
            raise InvalidFeatureTensorError(
                f"Unable to read feature stack: {feature_path}"
            ) from exc

        if array.ndim != 3:
            raise InvalidFeatureTensorError(
                f"Feature tensor must be 3D (C, H, W), received shape {array.shape}"
            )
        if array.shape[0] != CHANNEL_COUNT:
            raise InvalidFeatureTensorError(
                f"Expected {CHANNEL_COUNT} channels, received {array.shape[0]}"
            )
        return array

    def _load_label(self, sample_dir: Path) -> np.ndarray:
        label_path = sample_dir / "label.tif"
        if not label_path.exists():
            raise InvalidLabelError(f"Missing label raster for sample: {label_path}")

        try:
            with rasterio.open(label_path) as dataset:
                raw = dataset.read(1).astype(np.float64)
                nodata = (
                    dataset.nodata
                    if dataset.nodata is not None
                    else self.feature_nodata
                )
        except rasterio.errors.RasterioIOError as exc:
            raise InvalidLabelError(
                f"Unable to read label raster: {label_path}"
            ) from exc

        encoded = np.full(raw.shape, self.label_nodata, dtype=np.int64)
        class_count = len(self.manifest.label_classes)

        for flat_index, value in np.ndenumerate(raw):
            if not np.isfinite(value):
                continue
            if value == nodata or value == self.feature_nodata:
                continue

            class_index = int(round(value))
            if 0 <= class_index < class_count:
                encoded[flat_index] = class_index
                continue
            if 1 <= class_index <= class_count:
                encoded[flat_index] = class_index - 1
                continue

            raise InvalidLabelError(
                f"Unsupported label value '{value}' in sample '{sample_dir.name}'"
            )

        return encoded

    def _build_valid_mask(self, features: np.ndarray) -> np.ndarray:
        valid = np.all(features != self.feature_nodata, axis=0)
        return valid
