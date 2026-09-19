"""SSRI offline geospatial inference pipeline."""

from ssri_model.inference.config import InferenceConfig
from ssri_model.inference.exceptions import (
    InferenceAlignmentError,
    InferenceCheckpointError,
    InferenceError,
    InferenceInputError,
    InvalidInferenceConfigError,
)
from ssri_model.inference.metadata import INFERENCE_JSON_NAME
from ssri_model.inference.predictions import (
    save_confidence_raster,
    save_prediction_raster,
    save_probability_raster,
)
from ssri_model.inference.runner import InferenceResult, InferenceRunner, run_inference
from ssri_model.inference.safety import validate_inference_setup

__all__ = [
    "INFERENCE_JSON_NAME",
    "InferenceAlignmentError",
    "InferenceCheckpointError",
    "InferenceConfig",
    "InferenceError",
    "InferenceInputError",
    "InferenceResult",
    "InferenceRunner",
    "InvalidInferenceConfigError",
    "run_inference",
    "save_confidence_raster",
    "save_prediction_raster",
    "save_probability_raster",
    "validate_inference_setup",
]
