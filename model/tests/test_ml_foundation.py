"""Tests for the SSRI Stage 2 ML foundation."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from ssri_model.ml.constants import (
    CHANNEL_COUNT,
    CHANNEL_NAMES,
    DEFAULT_RANDOM_SEED,
    DEFAULT_RESOLUTION,
    DEFAULT_SPLIT,
    SUPPORTED_LABELS,
)
from ssri_model.ml.dataset_spec import DatasetManifest, FeatureSample
from ssri_model.ml.labels import LabelClass, is_supported_label, label_class_names
from ssri_model.ml.metadata import SampleMetadata
from ssri_model.ml.normalization import (
    CHANNEL_NORMALIZATION,
    NormalizationConfig,
    NormalizationMethod,
    validate_normalization_config,
)
from ssri_model.ml.splits import SplitConfig, split_sample_ids


class TestChannelSpecification:
    def test_channel_count(self) -> None:
        assert CHANNEL_COUNT == 13

    def test_channel_order_matches_stage1(self) -> None:
        expected = (
            "elevation",
            "slope",
            "plan_curvature",
            "profile_curvature",
            "twi",
            "relative_relief",
            "valley_depth",
            "ndvi",
            "ndwi",
            "clay_mineral_ratio",
            "iron_oxide_index",
            "gravity",
            "magnetics",
        )
        assert CHANNEL_NAMES == expected


class TestLabelSpecification:
    def test_enum_values(self) -> None:
        assert LabelClass.SUBSIDENCE.value == "subsidence"
        assert LabelClass.LANDSLIDE.value == "landslide"
        assert LabelClass.SINKHOLE.value == "sinkhole"

    def test_supported_labels_constant(self) -> None:
        assert SUPPORTED_LABELS == label_class_names()
        assert is_supported_label("landslide")
        assert not is_supported_label("earthquake")


class TestNormalizationConfiguration:
    def test_default_config_covers_all_channels(self) -> None:
        config = NormalizationConfig.default()
        validate_normalization_config(config)
        assert len(config.channel_methods) == CHANNEL_COUNT

    def test_channel_normalization_methods(self) -> None:
        assert CHANNEL_NORMALIZATION["ndvi"] == NormalizationMethod.IDENTITY
        assert CHANNEL_NORMALIZATION["elevation"] == NormalizationMethod.Z_SCORE
        assert CHANNEL_NORMALIZATION["slope"] == NormalizationMethod.MIN_MAX

    def test_normalization_round_trip(self) -> None:
        config = NormalizationConfig.default()
        restored = NormalizationConfig.from_dict(config.as_dict())
        assert restored.channel_methods == config.channel_methods


class TestDatasetManifest:
    def test_manifest_serialization(self, tmp_path: Path) -> None:
        manifest = DatasetManifest.create(
            dataset_name="ssri-demo",
            version="0.1.0",
            resolution=DEFAULT_RESOLUTION,
            crs="EPSG:32630",
            train_count=70,
            validation_count=15,
            test_count=15,
        )
        path = manifest.save(tmp_path / "dataset_manifest.json")
        loaded = DatasetManifest.load(path)

        assert loaded.dataset_name == "ssri-demo"
        assert loaded.channels == CHANNEL_NAMES
        assert loaded.label_classes == SUPPORTED_LABELS
        assert loaded.normalization == NormalizationConfig.default().as_dict()
        assert loaded.train_count == 70

    def test_feature_sample_serialization(self) -> None:
        sample = FeatureSample(
            sample_id="tile-001",
            feature_path="features/tile-001.npy",
            label_path="labels/tile-001.npy",
            metadata_path="metadata/tile-001.json",
        )
        restored = FeatureSample.from_dict(sample.to_dict())
        assert restored.sample_id == sample.sample_id
        assert Path(restored.feature_path) == Path(sample.feature_path)


class TestSampleMetadata:
    def test_metadata_serialization(self, tmp_path: Path) -> None:
        metadata = SampleMetadata(
            sample_id="tile-001",
            aoi={"bbox_wgs84": {"min_lon": -1.0, "min_lat": 50.0, "max_lon": 1.0, "max_lat": 52.0}},
            acquisition={"start_date": "2024-01-01", "end_date": "2024-02-01"},
            resolution_m=DEFAULT_RESOLUTION,
            crs="EPSG:32630",
            sources={"dem": "COP30", "gravity_provider": "wgm2012_bouguer"},
            package_version="0.1.0",
            created_at="2026-08-07T09:00:00+00:00",
        )
        path = metadata.save(tmp_path / "tile-001.json")
        loaded = SampleMetadata.load(path)
        payload = json.loads(path.read_text(encoding="utf-8"))

        assert loaded.sample_id == metadata.sample_id
        assert loaded.crs == metadata.crs
        assert payload["sources"]["dem"] == "COP30"


class TestDatasetSplits:
    def test_deterministic_splits(self) -> None:
        sample_ids = [f"sample-{index:03d}" for index in range(100)]
        config = SplitConfig(
            train=DEFAULT_SPLIT["train"],
            validation=DEFAULT_SPLIT["validation"],
            test=DEFAULT_SPLIT["test"],
            random_seed=DEFAULT_RANDOM_SEED,
        )

        first = split_sample_ids(sample_ids, config)
        second = split_sample_ids(sample_ids, config)

        assert first == second
        assert len(first.train) == 70
        assert len(first.validation) == 15
        assert len(first.test) == 15

    def test_split_assigns_all_samples_once(self) -> None:
        sample_ids = [f"sample-{index}" for index in range(23)]
        split = split_sample_ids(sample_ids)

        assigned = set(split.train) | set(split.validation) | set(split.test)
        assert assigned == set(sample_ids)
        assert len(assigned) == len(sample_ids)

    def test_invalid_split_proportions_raise(self) -> None:
        with pytest.raises(ValueError, match="sum to 1.0"):
            SplitConfig(train=0.5, validation=0.3, test=0.3)
