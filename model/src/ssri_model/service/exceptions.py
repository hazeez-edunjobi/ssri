"""Exceptions for SSRI service contracts."""


class ServiceError(Exception):
    """Base exception for service contract errors."""


class InvalidServiceConfigError(ServiceError):
    """Raised when service configuration is invalid."""


class InvalidServiceRequestError(ServiceError):
    """Raised when a service request is invalid."""


class PathSafetyError(ServiceError):
    """Raised when a path or identifier fails safety checks."""


class OutputFormatError(ServiceError):
    """Raised when an output format value is unsupported."""


class ScientificGateError(ServiceError):
    """Raised when scientific validation policy blocks serving."""
