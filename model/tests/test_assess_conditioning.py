"""Conditioning-feature sampling for assessments (lineaments / overburden)."""

from __future__ import annotations

import numpy as np
import torch

from ssri_model.api.assess_conditioning import sample_conditioning_features
from ssri_model.ml.constants import CHANNEL_COUNT, FEATURE_NODATA
from ssri_model.release_shell.channel_schema import CHANNEL_NAMES_V2


def test_v1_stack_marks_conditioning_unavailable() -> None:
    tensor = torch.zeros(1, CHANNEL_COUNT, 8, 8)
    payload = sample_conditioning_features(tensor, pixel_row=3, pixel_col=4)
    for name in ("overburden_thickness", "lineament_density", "lineament_distance"):
        assert payload["layers"][name]["status"] == "unavailable"
        assert payload["layers"][name]["value"] is None


def test_v2_stack_reports_available_and_nodata() -> None:
    array = np.full((16, 8, 8), FEATURE_NODATA, dtype=np.float32)
    array[13, 2, 3] = 12.5  # overburden_thickness
    array[14, 2, 3] = 0.4  # lineament_density
    # lineament_distance remains nodata
    payload = sample_conditioning_features(
        array,
        channel_names=CHANNEL_NAMES_V2,
        pixel_row=2,
        pixel_col=3,
    )
    assert payload["layers"]["overburden_thickness"]["status"] == "available"
    assert payload["layers"]["overburden_thickness"]["value"] == 12.5
    assert "thickness" in payload["layers"]["overburden_thickness"]["unit"]
    assert payload["layers"]["lineament_density"]["status"] == "available"
    assert payload["layers"]["lineament_distance"]["status"] == "nodata"
    assert payload["layers"]["lineament_distance"]["value"] is None


def test_out_of_range_pixel_uses_tensor_centre() -> None:
    array = np.zeros((16, 5, 5), dtype=np.float32)
    array[13, 2, 2] = 7.0
    payload = sample_conditioning_features(
        array,
        channel_names=CHANNEL_NAMES_V2,
        pixel_row=99,
        pixel_col=99,
    )
    assert payload["sample_policy"] == "tensor_centre"
    assert payload["layers"]["overburden_thickness"]["value"] == 7.0
