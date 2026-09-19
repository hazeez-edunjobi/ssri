"""Tests for SSRI offline inference pipeline."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
import torch

from ssri_model.inference import (
    INFERENCE_JSON_NAME,
    InferenceConfig,
    InferenceRunner,
    run_inference,
    validate_inference_setup,
)
from ssri_model.inference.checkpoint import load_inference_checkpoint
from ssri_model.inference.exceptions import (
    InferenceCheckpointError,
    InferenceInputError,
    InvalidInferenceConfigError,
)
from ssri_model.inference.tiling import generate_windows
from ssri_model.ml.constants import CHANNEL_COUNT, CHANNEL_NAMES, LABEL_NODATA
from ssri_model.ml.exceptions import StatisticsError
from tests.inference_helpers import (
    build_inference_inputs,
    save_inference_checkpoint,
    write_feature_stack,
    write_stage1_manifest,
    write_statistics,
)


class TestInferenceConfig:
    def test_valid_configuration(self, tmp_path: Path) -> None:
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "best.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
        )
        assert config.tile_size == 512
        assert config.overlap == 64
        assert config.batch_size == 4

    def test_invalid_tile_size(self) -> None:
        with pytest.raises(InvalidInferenceConfigError):
            InferenceConfig(
                checkpoint_path="a.pt",
                feature_path="f.npy",
                manifest_path="m.json",
                statistics_path="s.json",
                output_dir="out",
                tile_size=0,
            )

    def test_invalid_overlap(self) -> None:
        with pytest.raises(InvalidInferenceConfigError):
            InferenceConfig(
                checkpoint_path="a.pt",
                feature_path="f.npy",
                manifest_path="m.json",
                statistics_path="s.json",
                output_dir="out",
                overlap=512,
            )

    def test_mixed_precision_rejected_on_cpu(self) -> None:
        with pytest.raises(InvalidInferenceConfigError):
            InferenceConfig(
                checkpoint_path="a.pt",
                feature_path="f.npy",
                manifest_path="m.json",
                statistics_path="s.json",
                output_dir="out",
                device="cpu",
                mixed_precision=True,
            )


class TestValidateInferenceSetup:
    def test_missing_checkpoint(self, tmp_path: Path) -> None:
        feature_path, manifest_path, statistics_path, _, _ = build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "missing.pt"),
            feature_path=str(feature_path),
            manifest_path=str(manifest_path),
            statistics_path=str(statistics_path),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(InvalidInferenceConfigError):
            validate_inference_setup(config)

    def test_missing_feature(self, tmp_path: Path) -> None:
        _, manifest_path, statistics_path, checkpoint_path, _ = build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(tmp_path / "missing.npy"),
            manifest_path=str(manifest_path),
            statistics_path=str(statistics_path),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(InferenceInputError):
            validate_inference_setup(config)

    def test_missing_manifest(self, tmp_path: Path) -> None:
        feature_path, _, statistics_path, checkpoint_path, _ = build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(feature_path),
            manifest_path=str(tmp_path / "missing.json"),
            statistics_path=str(statistics_path),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(InvalidInferenceConfigError):
            validate_inference_setup(config)

    def test_missing_statistics(self, tmp_path: Path) -> None:
        feature_path, manifest_path, _, checkpoint_path, _ = build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(feature_path),
            manifest_path=str(manifest_path),
            statistics_path=str(tmp_path / "missing.json"),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(InvalidInferenceConfigError):
            validate_inference_setup(config)

    def test_channel_count_mismatch(self, tmp_path: Path) -> None:
        feature_path, manifest_path, statistics_path, checkpoint_path, _ = build_inference_inputs(
            tmp_path
        )
        bad = np.zeros((12, 16, 16), dtype=np.float64)
        np.save(feature_path, bad)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(feature_path),
            manifest_path=str(manifest_path),
            statistics_path=str(statistics_path),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(InferenceInputError, match="13 channels"):
            validate_inference_setup(config)

    def test_channel_order_mismatch(self, tmp_path: Path) -> None:
        root = tmp_path / "bad-order"
        root.mkdir()
        feature_path = root / "feature_stack.npy"
        manifest_path = root / "manifest.json"
        statistics_path = root / "statistics.json"
        checkpoint_path = root / "checkpoint.pt"
        tensor = write_feature_stack(feature_path)
        write_stage1_manifest(
            manifest_path,
            channel_names=tuple(reversed(CHANNEL_NAMES)),
        )
        write_statistics(statistics_path, [tensor])
        save_inference_checkpoint(checkpoint_path)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(feature_path),
            manifest_path=str(manifest_path),
            statistics_path=str(statistics_path),
            output_dir=str(root / "out"),
        )
        with pytest.raises(InferenceInputError, match="channel order"):
            validate_inference_setup(config)

    def test_statistics_channel_mismatch(self, tmp_path: Path) -> None:
        feature_path, manifest_path, statistics_path, checkpoint_path, _ = build_inference_inputs(
            tmp_path
        )
        statistics_path.write_text(
            json.dumps({"channel_stats": {"elevation": {"min": 0, "max": 1, "mean": 0.5, "std": 1}}}),
            encoding="utf-8",
        )
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(feature_path),
            manifest_path=str(manifest_path),
            statistics_path=str(statistics_path),
            output_dir=str(tmp_path / "out"),
        )
        with pytest.raises(StatisticsError):
            validate_inference_setup(config)


class TestCheckpointLoading:
    def test_load_checkpoint_restores_model_config(self, tmp_path: Path) -> None:
        _, _, _, checkpoint_path, _ = build_inference_inputs(tmp_path)
        device = torch.device("cpu")
        model, payload = load_inference_checkpoint(checkpoint_path, device=device)
        assert model.in_channels == CHANNEL_COUNT
        assert model.num_classes == 3
        assert isinstance(payload["model_config"], dict)

    def test_invalid_checkpoint_rejected(self, tmp_path: Path) -> None:
        bad_path = tmp_path / "bad.pt"
        bad_path.write_text("not-a-checkpoint", encoding="utf-8")
        with pytest.raises(InferenceCheckpointError):
            load_inference_checkpoint(bad_path, device=torch.device("cpu"))


class TestRunInference:
    def test_small_synthetic_inference(self, tmp_path: Path) -> None:
        feature_path, manifest_path, statistics_path, checkpoint_path, _ = build_inference_inputs(
            tmp_path,
            width=16,
            height=16,
        )
        output_dir = tmp_path / "predictions"
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(feature_path),
            manifest_path=str(manifest_path),
            statistics_path=str(statistics_path),
            output_dir=str(output_dir),
            tile_size=8,
            overlap=2,
            batch_size=2,
            device="cpu",
        )
        result = run_inference(config)
        assert result.prediction.shape == (16, 16)
        assert result.confidence.shape == (16, 16)
        assert result.probabilities.shape == (3, 16, 16)
        assert result.mask.shape == (16, 16)
        assert result.prediction_path.exists()
        assert result.confidence_path.exists()
        assert result.probabilities_path.exists()
        assert result.metadata_path.exists()

    def test_output_dtypes(self, tmp_path: Path) -> None:
        _, _, _, checkpoint_path, _ = build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=8,
            overlap=2,
            device="cpu",
        )
        result = run_inference(config)
        assert result.prediction.dtype == np.int64
        assert result.confidence.dtype == np.float32
        assert result.probabilities.dtype == np.float32
        assert result.mask.dtype == np.bool_

    def test_probability_sum_and_confidence(self, tmp_path: Path) -> None:
        _, _, _, checkpoint_path, _ = build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(checkpoint_path),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=8,
            overlap=2,
            device="cpu",
        )
        result = run_inference(config)
        valid = result.mask
        sums = result.probabilities[:, valid].sum(axis=0)
        assert np.allclose(sums, 1.0, atol=1e-5)
        assert np.allclose(
            result.confidence[valid],
            result.probabilities[:, valid].max(axis=0),
            atol=1e-5,
        )

    def test_invalid_pixels_output_nodata_and_zero(self, tmp_path: Path) -> None:
        invalid = np.zeros((16, 16), dtype=bool)
        invalid[0, :] = True
        build_inference_inputs(tmp_path, invalid_mask=invalid)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=8,
            overlap=2,
            device="cpu",
        )
        result = run_inference(config)
        assert np.all(result.prediction[0, :] == LABEL_NODATA)
        assert np.all(result.confidence[0, :] == 0.0)
        assert np.all(result.probabilities[:, 0, :] == 0.0)

    def test_odd_dimensions(self, tmp_path: Path) -> None:
        build_inference_inputs(tmp_path, width=101, height=137)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=64,
            overlap=16,
            batch_size=2,
            device="cpu",
        )
        result = run_inference(config)
        assert result.prediction.shape == (137, 101)

    def test_large_grid_windowed_inference(self, tmp_path: Path) -> None:
        build_inference_inputs(tmp_path, width=1001, height=777)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=128,
            overlap=32,
            batch_size=2,
            device="cpu",
        )
        result = run_inference(config)
        assert result.prediction.shape == (777, 1001)

    def test_overlap_blending_is_deterministic(self, tmp_path: Path) -> None:
        build_inference_inputs(tmp_path, width=64, height=64)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=32,
            overlap=8,
            batch_size=1,
            device="cpu",
        )
        first = run_inference(config)
        second = run_inference(config)
        assert np.array_equal(first.prediction, second.prediction)
        assert np.allclose(first.probabilities, second.probabilities)

    def test_inference_runner_wrapper(self, tmp_path: Path) -> None:
        build_inference_inputs(tmp_path)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=8,
            overlap=2,
            device="cpu",
        )
        result = InferenceRunner(config).run()
        assert result.prediction.shape == (16, 16)


class TestGeoTiffOutputs:
    def test_crs_transform_dimensions_and_bands(self, tmp_path: Path) -> None:
        build_inference_inputs(tmp_path, width=32, height=24)
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(tmp_path / "out"),
            tile_size=16,
            overlap=4,
            device="cpu",
        )
        result = run_inference(config)
        manifest = json.loads((tmp_path / "manifest.json").read_text(encoding="utf-8"))
        expected_crs = manifest["crs"]
        expected_transform = manifest["projection"]["transform"]

        with rasterio.open(result.prediction_path) as prediction:
            assert prediction.crs.to_string() == expected_crs
            assert list(prediction.transform) == pytest.approx(expected_transform)
            assert prediction.width == 32
            assert prediction.height == 24
            assert prediction.nodata == LABEL_NODATA

        with rasterio.open(result.confidence_path) as confidence:
            assert confidence.crs.to_string() == expected_crs
            assert list(confidence.transform) == pytest.approx(expected_transform)
            assert confidence.width == 32
            assert confidence.height == 24

        with rasterio.open(result.probabilities_path) as probabilities:
            assert probabilities.crs.to_string() == expected_crs
            assert list(probabilities.transform) == pytest.approx(expected_transform)
            assert probabilities.count == 3
            assert probabilities.descriptions == (
                "subsidence_probability",
                "landslide_probability",
                "sinkhole_probability",
            )


class TestInferenceMetadata:
    def test_inference_json_written(self, tmp_path: Path) -> None:
        build_inference_inputs(tmp_path)
        output_dir = tmp_path / "out"
        config = InferenceConfig(
            checkpoint_path=str(tmp_path / "checkpoint.pt"),
            feature_path=str(tmp_path / "feature_stack.npy"),
            manifest_path=str(tmp_path / "manifest.json"),
            statistics_path=str(tmp_path / "statistics.json"),
            output_dir=str(output_dir),
            tile_size=8,
            overlap=2,
            device="cpu",
        )
        run_inference(config)
        metadata_path = output_dir / INFERENCE_JSON_NAME
        payload = json.loads(metadata_path.read_text(encoding="utf-8"))
        assert payload["scientific_validation_status"] == "NOT_VALIDATED"
        assert payload["input"]["shape"] == [CHANNEL_COUNT, 16, 16]
        assert payload["inference"]["tile_size"] == 8
        assert payload["outputs"]["prediction"].endswith("prediction.tif")


class TestTiling:
    def test_windows_cover_odd_dimensions(self) -> None:
        windows = generate_windows(137, 101, tile_size=64, overlap=16)
        covered = np.zeros((137, 101), dtype=bool)
        for window in windows:
            covered[
                window.row : window.row + window.height,
                window.col : window.col + window.width,
            ] = True
        assert covered.all()

    def test_overlap_blending_weights_are_uniform(self) -> None:
        weights = __import__(
            "ssri_model.inference.tiling", fromlist=["uniform_blend_weights"]
        ).uniform_blend_weights(32, 32)
        assert np.allclose(weights, 1.0)
