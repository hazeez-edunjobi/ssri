"""Typed exceptions for SSRI model architecture."""

from __future__ import annotations


class SSRIArchitectureError(Exception):
    """Base exception for SSRI architecture errors."""


class InvalidModelConfigError(SSRIArchitectureError):
    """Raised when model configuration values are invalid."""


class InvalidInputTensorError(SSRIArchitectureError):
    """Raised when model input violates the SSRI tensor contract."""
