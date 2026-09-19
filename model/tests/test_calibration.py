"""Calibration report helpers — no fabricated metrics."""

from __future__ import annotations

import numpy as np
import pytest

from ssri_model.evaluation.calibration import (
    binary_confusion_at_threshold,
    build_calibration_report,
    mann_whitney_auc,
    save_calibration_report,
)


def test_perfect_separator_auc_near_one() -> None:
    y_true = np.array([0, 0, 0, 1, 1, 1], dtype=float)
    y_score = np.array([0.1, 0.2, 0.3, 0.7, 0.8, 0.9], dtype=float)
    auc = mann_whitney_auc(y_true, y_score)
    assert auc == 1.0


def test_confusion_matrix_counts() -> None:
    y_true = np.array([1, 0, 1, 0], dtype=float)
    y_score = np.array([0.9, 0.1, 0.4, 0.6], dtype=float)
    conf = binary_confusion_at_threshold(y_true, y_score, threshold=0.5)
    assert conf["tp"] == 1
    assert conf["tn"] == 1
    assert conf["fp"] == 1
    assert conf["fn"] == 1


def test_pending_when_no_arrays() -> None:
    report = build_calibration_report(
        y_true=None,
        y_score=None,
        dataset_name="unset",
        dataset_version="unset",
        model_version="ssri-model",
    )
    assert report["status"] == "PENDING_REAL_DATA"
    assert report["metrics"] is None


def test_save_calibration_report(tmp_path) -> None:
    report = build_calibration_report(
        y_true=None,
        y_score=None,
        dataset_name="unset",
        dataset_version="unset",
        model_version="ssri-model",
    )
    path = save_calibration_report(tmp_path / "calibration.json", report)
    assert path.exists()
