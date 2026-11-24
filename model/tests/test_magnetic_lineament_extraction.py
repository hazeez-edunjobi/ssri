"""Tests for candidate magnetic lineament extraction (not fault mapping)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from ssri_model.geological.magnetic_lineament_extraction import (
    ExtractionParams,
    SCIENTIFIC_CLASS,
    run_candidate_lineament_extraction,
    write_extraction_outputs,
)


def _synthetic_ridge_grid(
    n: int = 64,
) -> tuple[np.ndarray, np.ndarray, np.ndarray, np.ndarray]:
    """THG-like field with a NE–SW ridge; TMI/gaussian for residual blend."""
    yy, xx = np.mgrid[0:n, 0:n]
    # Diagonal ridge distance
    dist = np.abs(xx - yy) / np.sqrt(2.0)
    thg = np.exp(-((dist / 2.5) ** 2)) * 10.0
    # Add mild noise
    rng = np.random.default_rng(0)
    thg = thg + rng.normal(0, 0.05, size=thg.shape)
    mask = np.ones((n, n), dtype=bool)
    tmi = thg * 3.0 + 1000.0
    gaussian = np.full_like(tmi, float(np.mean(tmi)))
    return thg, tmi, gaussian, mask


def test_extraction_produces_candidate_geojson_not_faults():
    thg, tmi, gaussian, mask = _synthetic_ridge_grid()
    result = run_candidate_lineament_extraction(
        thg=thg,
        analytic=None,
        tmi=tmi,
        gaussian=gaussian,
        mask=mask,
        xmin=500_000.0,
        ymax=800_000.0,
        dx=100.0,
        dy=100.0,
        processing_crs="EPSG:32631",
        params=ExtractionParams(percentile=85.0, min_length_cells=3, min_component_cells=4),
    )
    assert result["scientific_validation_status"] == "NOT_VALIDATED"
    assert result["not_confirmed_faults_or_fractures"] is True
    assert result["used_in_inference"] is False
    assert result["geojson"]["properties"]["scientific_class"] == SCIENTIFIC_CLASS
    assert result["statistics"]["n_lineaments"] >= 1
    for feat in result["features"]:
        assert feat["properties"]["not_confirmed_fault"] is True
        assert feat["properties"]["scientific_class"] == SCIENTIFIC_CLASS
    assert result["density"].shape == mask.shape
    assert result["distance"].shape == mask.shape


def test_write_extraction_outputs(tmp_path: Path):
    thg, tmi, gaussian, mask = _synthetic_ridge_grid(48)
    result = run_candidate_lineament_extraction(
        thg=thg,
        analytic=None,
        tmi=tmi,
        gaussian=gaussian,
        mask=mask,
        xmin=1000.0,
        ymax=2000.0,
        dx=50.0,
        dy=50.0,
        processing_crs="EPSG:32631",
        params=ExtractionParams(percentile=80.0, min_length_cells=2, min_component_cells=3),
    )
    qc = write_extraction_outputs(result, tmp_path / "lineaments")
    assert (tmp_path / "lineaments" / "candidate_lineaments.geojson").is_file()
    assert (tmp_path / "lineaments" / "lineament_density.tif").is_file()
    assert (tmp_path / "lineaments" / "lineament_distance.tif").is_file()
    assert (tmp_path / "lineaments" / "lineament_extraction_qc.json").is_file()
    assert qc["not_confirmed_faults_or_fractures"] is True
    payload = json.loads(
        (tmp_path / "lineaments" / "candidate_lineaments.geojson").read_text(encoding="utf-8")
    )
    assert payload["properties"]["not_confirmed_faults_or_fractures"] is True


def test_requires_enhancement_source():
    mask = np.ones((8, 8), dtype=bool)
    with pytest.raises(ValueError, match="first_horizontal_derivative|analytic_signal"):
        run_candidate_lineament_extraction(
            thg=None,
            analytic=None,
            tmi=None,
            gaussian=None,
            mask=mask,
            xmin=0.0,
            ymax=800.0,
            dx=100.0,
            dy=100.0,
            processing_crs="EPSG:32631",
        )
