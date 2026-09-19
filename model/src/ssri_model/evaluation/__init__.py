"""SSRI held-out test-set evaluation."""

from ssri_model.evaluation.config import EvaluationConfig
from ssri_model.evaluation.evaluator import (
    EvaluationResult,
    Evaluator,
    SampleEvaluationResult,
    evaluate_checkpoint,
    load_evaluation_model,
)
from ssri_model.evaluation.exceptions import (
    EvaluationCheckpointError,
    EvaluationDataLeakageError,
    EvaluationError,
    InvalidEvaluationConfigError,
    PredictionAlignmentError,
)
from ssri_model.evaluation.metrics import (
    EvaluationMetrics,
    compute_evaluation_metrics,
    compute_evaluation_metrics_from_confusion,
)
from ssri_model.evaluation.predictions import (
    logits_to_confidence,
    logits_to_probabilities,
    read_label_grid,
    save_confidence_raster,
    save_prediction_raster,
    save_probability_raster,
)
from ssri_model.evaluation.report import (
    CONFUSION_MATRIX_JSON_NAME,
    EVALUATION_JSON_NAME,
    EVALUATION_MD_NAME,
    SAMPLE_RESULTS_JSON_NAME,
)
from ssri_model.evaluation.safety import check_test_split_leakage, validate_evaluation_setup

__all__ = [
    "CONFUSION_MATRIX_JSON_NAME",
    "EVALUATION_JSON_NAME",
    "EVALUATION_MD_NAME",
    "EvaluationCheckpointError",
    "EvaluationConfig",
    "EvaluationDataLeakageError",
    "EvaluationError",
    "EvaluationMetrics",
    "EvaluationResult",
    "Evaluator",
    "InvalidEvaluationConfigError",
    "PredictionAlignmentError",
    "SAMPLE_RESULTS_JSON_NAME",
    "SampleEvaluationResult",
    "check_test_split_leakage",
    "compute_evaluation_metrics",
    "compute_evaluation_metrics_from_confusion",
    "evaluate_checkpoint",
    "load_evaluation_model",
    "logits_to_confidence",
    "logits_to_probabilities",
    "read_label_grid",
    "save_confidence_raster",
    "save_prediction_raster",
    "save_probability_raster",
    "validate_evaluation_setup",
]
