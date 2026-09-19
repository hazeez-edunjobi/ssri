"""SSRI neural network architecture."""

from ssri_model.architecture.config import SSRIModelConfig
from ssri_model.architecture.exceptions import (
    InvalidInputTensorError,
    InvalidModelConfigError,
    SSRIArchitectureError,
)
from ssri_model.architecture.model import (
    ParameterSummary,
    SSRIModel,
    count_parameters,
    create_ssri_model,
    format_parameter_summary,
)

__all__ = [
    "InvalidInputTensorError",
    "InvalidModelConfigError",
    "ParameterSummary",
    "SSRIArchitectureError",
    "SSRIModel",
    "SSRIModelConfig",
    "count_parameters",
    "create_ssri_model",
    "format_parameter_summary",
]
