"""Authentication and authorization exceptions."""


class AuthError(Exception):
    """Base exception for authentication/authorization errors."""


class InvalidAuthConfigError(AuthError):
    """Raised when authentication configuration is invalid."""


class AuthenticationError(AuthError):
    """Raised when authentication fails."""


class AuthorizationError(AuthError):
    """Raised when the principal lacks required permissions."""
