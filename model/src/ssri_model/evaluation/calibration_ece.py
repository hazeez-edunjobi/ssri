"""Expected Calibration Error and reliability helpers.

Scientific ECE on real held-out data is a separate validation milestone.
These functions compute ECE correctly when given real probability/label pairs.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np


@dataclass(frozen=True)
class CalibrationResult:
    """ECE summary with per-bin statistics."""

    ece: float
    n_bins: int
    bin_confidence: tuple[float, ...]
    bin_accuracy: tuple[float, ...]
    bin_counts: tuple[int, ...]


def expected_calibration_error(
    probabilities: np.ndarray,
    labels: np.ndarray,
    *,
    n_bins: int = 15,
) -> CalibrationResult:
    """Compute ECE for binary labels in ``{0,1}`` and probabilities in ``[0,1]``.

    Uses equal-width bins on predicted probability.
    """
    probs = np.asarray(probabilities, dtype=np.float64).ravel()
    y = np.asarray(labels, dtype=np.float64).ravel()
    if probs.shape != y.shape:
        raise ValueError("probabilities and labels must share shape")
    if n_bins < 2:
        raise ValueError("n_bins must be >= 2")
    if probs.size == 0:
        raise ValueError("empty inputs")

    bin_edges = np.linspace(0.0, 1.0, n_bins + 1)
    confidences: list[float] = []
    accuracies: list[float] = []
    counts: list[int] = []
    ece = 0.0
    total = float(probs.size)
    for i in range(n_bins):
        left = bin_edges[i]
        right = bin_edges[i + 1]
        if i == n_bins - 1:
            mask = (probs >= left) & (probs <= right)
        else:
            mask = (probs >= left) & (probs < right)
        count = int(mask.sum())
        counts.append(count)
        if count == 0:
            confidences.append(float("nan"))
            accuracies.append(float("nan"))
            continue
        conf = float(probs[mask].mean())
        acc = float(y[mask].mean())
        confidences.append(conf)
        accuracies.append(acc)
        ece += (count / total) * abs(acc - conf)

    return CalibrationResult(
        ece=float(ece),
        n_bins=n_bins,
        bin_confidence=tuple(confidences),
        bin_accuracy=tuple(accuracies),
        bin_counts=tuple(counts),
    )
