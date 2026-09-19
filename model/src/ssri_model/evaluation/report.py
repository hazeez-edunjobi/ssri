"""Evaluation report generation for SSRI."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ssri_model.ml.constants import CHANNEL_NAMES
from ssri_model.ml.labels import label_class_names


EVALUATION_JSON_NAME = "evaluation.json"
EVALUATION_MD_NAME = "evaluation.md"
CONFUSION_MATRIX_JSON_NAME = "confusion_matrix.json"
SAMPLE_RESULTS_JSON_NAME = "sample_results.json"


def save_confusion_matrix(path: Path | str, payload: dict[str, Any]) -> Path:
    """Write a labelled confusion matrix JSON file."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def save_evaluation_json(path: Path | str, payload: dict[str, Any]) -> Path:
    """Write the structured evaluation result JSON."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def save_sample_results(path: Path | str, payload: list[dict[str, Any]]) -> Path:
    """Write per-sample evaluation metrics."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return destination


def render_evaluation_markdown(payload: dict[str, Any]) -> str:
    """Render a human-readable evaluation report."""
    class_names = label_class_names()
    confusion = payload.get("confusion_matrix", {})
    matrix = confusion.get("matrix", [])
    columns = confusion.get("columns", class_names)

    lines = [
        "# SSRI Evaluation Report",
        "",
        "## Dataset",
        f"- Name: {payload.get('dataset_name')}",
        f"- Version: {payload.get('dataset_version')}",
        "",
        "## Checkpoint",
        f"- Path: {payload.get('checkpoint_path')}",
        f"- Epoch: {payload.get('checkpoint_epoch')}",
        f"- Best metric: {payload.get('checkpoint_metric')}",
        "",
        "## Model",
        f"- Configuration: {json.dumps(payload.get('model_config', {}), indent=2)}",
        f"- Input channels: {payload.get('channel_count')}",
        f"- Classes: {', '.join(class_names)}",
        "",
        "## Test Set",
        f"- Test samples: {payload.get('test_sample_count')}",
        f"- Evaluated samples: {payload.get('evaluated_sample_count')}",
        f"- Unevaluable samples: {payload.get('unevaluable_sample_count')}",
        f"- Valid pixels: {payload.get('valid_pixel_count')}",
        "",
        "## Overall Metrics",
        f"- Accuracy: {payload.get('overall_accuracy')}",
        f"- Macro precision: {payload.get('macro_precision')}",
        f"- Macro recall: {payload.get('macro_recall')}",
        f"- Macro F1: {payload.get('macro_f1')}",
        f"- Mean IoU: {payload.get('mean_iou')}",
        "",
        "## Per-Class Metrics",
    ]

    per_class = payload.get("per_class_metrics", {})
    for class_name in class_names:
        metrics = per_class.get(class_name, {})
        lines.extend(
            [
                f"### {class_name}",
                f"- Precision: {metrics.get('precision')}",
                f"- Recall: {metrics.get('recall')}",
                f"- F1: {metrics.get('f1')}",
                f"- IoU: {metrics.get('iou')}",
                "",
            ]
        )

    lines.extend(["## Confusion Matrix", "", "Rows = actual, columns = predicted", ""])
    header = "| actual \\\\ predicted | " + " | ".join(columns) + " |"
    separator = "| --- | " + " | ".join(["---"] * len(columns)) + " |"
    lines.extend([header, separator])
    for index, row in enumerate(matrix):
        row_label = class_names[index] if index < len(class_names) else str(index)
        lines.append("| " + row_label + " | " + " | ".join(str(value) for value in row) + " |")

    lines.extend(
        [
            "",
            "## Sample-Level Results",
            f"See `{SAMPLE_RESULTS_JSON_NAME}` for per-sample metrics.",
            "",
            "## Prediction Artifacts",
            f"- Predictions saved: {payload.get('save_predictions')}",
            f"- Probabilities saved: {payload.get('save_probabilities')}",
            f"- Confidence saved: {payload.get('save_confidence')}",
            "",
            "## Reproducibility",
            f"- Device: {payload.get('device')}",
            f"- Evaluation started: {payload.get('evaluation_started_at')}",
            f"- Evaluation completed: {payload.get('evaluation_completed_at')}",
            f"- Duration (seconds): {payload.get('evaluation_seconds')}",
            f"- Channel order: {', '.join(CHANNEL_NAMES)}",
            "",
            "## Limitations",
            "- Evaluation uses the held-out test split only.",
            "- Metrics exclude feature nodata and label nodata pixels.",
            "- Zero-division cases return 0.0 rather than NaN.",
            "",
            "## Scientific Validity",
            f"- Status: {payload.get('scientific_validation_status')}",
            "- Model confidence is the maximum softmax probability and has not "
            "been calibrated unless a separate calibration procedure is performed.",
            "- Successful engineering evaluation on synthetic or non-representative "
            "data does not establish real-world hazard prediction capability.",
            "",
        ]
    )
    return "\n".join(lines)


def save_evaluation_markdown(path: Path | str, payload: dict[str, Any]) -> Path:
    """Write the Markdown evaluation report."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(render_evaluation_markdown(payload), encoding="utf-8")
    return destination
