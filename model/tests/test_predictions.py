"""Tests for SSRI evaluation prediction artifacts."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest
import rasterio
import torch

from ssri_model.evaluation.predictions import (
    logits_to_confidence,
    logits_to_probabilities,
    read_label_grid,
    save_confidence_raster,
    save_prediction_raster,
    save_probability_raster,
)
from ssri_model.evaluation.exceptions import PredictionAlignmentError
from ssri_model.ml.constants import LABEL_NODATA
from tests.evaluation_helpers import write_sample


class TestPredictions:
    @pytest.fixture
    def sample_grid(self, tmp_path: Path):
        sample_dir = tmp_path / "test-a"
        write_sample(sample_dir, width=8, height=8, label_value=1.0)
        grid = read_label_grid(sample_dir / "label.tif")
        return sample_dir, grid

    def test_prediction_raster_shape(self, sample_grid: tuple, tmp_path: Path) -> None:
        _, grid = sample_grid
        predictions = torch.zeros(8, 8, dtype=torch.int64)
        mask = torch.ones(8, 8, dtype=torch.bool)
        path = save_prediction_raster(
            tmp_path / "prediction.tif",
            predictions,
            valid_mask=mask,
            grid=grid,
        )
        with rasterio.open(path) as dataset:
            assert dataset.width == 8
            assert dataset.height == 8

    def test_crs_and_transform_preserved(self, sample_grid: tuple, tmp_path: Path) -> None:
        _, grid = sample_grid
        predictions = torch.ones(8, 8, dtype=torch.int64)
        mask = torch.ones(8, 8, dtype=torch.bool)
        path = save_prediction_raster(
            tmp_path / "prediction.tif",
            predictions,
            valid_mask=mask,
            grid=grid,
        )
        with rasterio.open(path) as dataset:
            assert dataset.crs == grid.crs
            assert dataset.transform == grid.transform

    def test_invalid_pixels_become_nodata(self, sample_grid: tuple, tmp_path: Path) -> None:
        _, grid = sample_grid
        predictions = torch.full((8, 8), 2, dtype=torch.int64)
        mask = torch.ones(8, 8, dtype=torch.bool)
        mask[0, 0] = False
        path = save_prediction_raster(
            tmp_path / "prediction.tif",
            predictions,
            valid_mask=mask,
            grid=grid,
        )
        with rasterio.open(path) as dataset:
            data = dataset.read(1)
            assert int(data[0, 0]) == LABEL_NODATA

    def test_confidence_raster(self, sample_grid: tuple, tmp_path: Path) -> None:
        _, grid = sample_grid
        logits = torch.zeros(1, 3, 8, 8)
        logits[:, 0, :, :] = 5.0
        confidence = logits_to_confidence(logits)[0]
        mask = torch.ones(8, 8, dtype=torch.bool)
        path = save_confidence_raster(
            tmp_path / "confidence.tif",
            confidence,
            valid_mask=mask,
            grid=grid,
        )
        with rasterio.open(path) as dataset:
            assert dataset.count == 1

    def test_probability_raster_three_bands(self, sample_grid: tuple, tmp_path: Path) -> None:
        _, grid = sample_grid
        logits = torch.randn(1, 3, 8, 8)
        probabilities = logits_to_probabilities(logits)[0]
        mask = torch.ones(8, 8, dtype=torch.bool)
        path = save_probability_raster(
            tmp_path / "probabilities.tif",
            probabilities,
            valid_mask=mask,
            grid=grid,
        )
        with rasterio.open(path) as dataset:
            assert dataset.count == 3
            band_sum = np.sum(dataset.read()[ :, 0, 0])
            assert band_sum == pytest.approx(1.0, abs=1e-5)

    def test_probabilities_sum_to_one_on_valid_pixels(self) -> None:
        logits = torch.randn(1, 3, 4, 4)
        probabilities = logits_to_probabilities(logits)[0]
        totals = probabilities.sum(dim=0)
        assert torch.allclose(totals, torch.ones_like(totals), atol=1e-5)

    def test_alignment_error_on_shape_mismatch(self, sample_grid: tuple, tmp_path: Path) -> None:
        _, grid = sample_grid
        predictions = torch.zeros(4, 4, dtype=torch.int64)
        mask = torch.ones(4, 4, dtype=torch.bool)
        with pytest.raises(PredictionAlignmentError):
            save_prediction_raster(
                tmp_path / "prediction.tif",
                predictions,
                valid_mask=mask,
                grid=grid,
            )
