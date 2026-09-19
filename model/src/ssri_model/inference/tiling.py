"""Window generation and overlap blending for SSRI inference."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ssri_model.inference.exceptions import InvalidInferenceConfigError


@dataclass(frozen=True)
class InferenceWindow:
    """One inference window over a feature grid."""

    row: int
    col: int
    height: int
    width: int


def _window_starts(length: int, tile_size: int, overlap: int) -> list[int]:
    if length <= tile_size:
        return [0]
    stride = tile_size - overlap
    if stride <= 0:
        raise InvalidInferenceConfigError("overlap must be less than tile_size")
    starts = list(range(0, length - tile_size + 1, stride))
    last = length - tile_size
    if starts[-1] != last:
        starts.append(last)
    return starts


def generate_windows(
    height: int,
    width: int,
    *,
    tile_size: int,
    overlap: int,
) -> list[InferenceWindow]:
    """Generate window coordinates that fully cover an H×W grid."""
    row_starts = _window_starts(height, tile_size, overlap)
    col_starts = _window_starts(width, tile_size, overlap)

    windows: list[InferenceWindow] = []
    for row in row_starts:
        window_height = min(tile_size, height - row)
        for col in col_starts:
            window_width = min(tile_size, width - col)
            windows.append(
                InferenceWindow(
                    row=row,
                    col=col,
                    height=window_height,
                    width=window_width,
                )
            )
    return windows


def uniform_blend_weights(height: int, width: int) -> np.ndarray:
    """Return uniform overlap weights for a window.

    Stage 2.7 uses uniform weights: every pixel in the window contributes
    equally during overlap accumulation.
    """
    return np.ones((height, width), dtype=np.float32)
