"""SSRI API authentication and authorization."""

from ssri_model.auth.authorization import (
    has_permission,
    permissions_for_role,
    require_permission,
)
from ssri_model.auth.models import Permission
from ssri_model.auth.config import AuthConfig
from ssri_model.auth.credentials import KeyStore, generate_api_key, parse_api_key, redact_api_key
from ssri_model.auth.exceptions import (
    AuthenticationError,
    AuthorizationError,
    InvalidAuthConfigError,
)
from ssri_model.auth.models import (
    APIKeyRecord,
    AuthenticatedPrincipal,
    GeneratedAPIKey,
    Role,
)

__all__ = [
    "APIKeyRecord",
    "AuthConfig",
    "AuthenticatedPrincipal",
    "AuthenticationError",
    "AuthorizationError",
    "GeneratedAPIKey",
    "KeyStore",
    "InvalidAuthConfigError",
    "Permission",
    "Role",
    "generate_api_key",
    "has_permission",
    "parse_api_key",
    "permissions_for_role",
    "redact_api_key",
    "require_permission",
]
