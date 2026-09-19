"""FastAPI authentication dependencies."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ssri_model.auth.audit import log_authentication_event
from ssri_model.auth.authorization import permissions_for_role, require_permission
from ssri_model.auth.config import AuthConfig
from ssri_model.auth.credentials import KeyStore, is_key_active, parse_api_key
from ssri_model.auth.exceptions import AuthenticationError
from ssri_model.auth.hashing import verify_api_key_secret
from ssri_model.auth.models import AuthenticatedPrincipal, Permission, Role

_bearer_scheme = HTTPBearer(auto_error=False)


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def development_principal() -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        key_id="development",
        role=Role.OPERATOR,
        permissions=permissions_for_role(Role.OPERATOR),
        authentication_method="disabled",
        authenticated_at=utc_now_iso(),
    )


def authenticate_api_key(
    *,
    auth_config: AuthConfig,
    key_store: KeyStore,
    token: str,
) -> AuthenticatedPrincipal:
    try:
        key_id, secret = parse_api_key(token)
    except AuthenticationError as exc:
        raise AuthenticationError("Invalid authentication credentials.") from exc

    record = key_store.get(key_id)
    if record is None:
        raise AuthenticationError("Invalid authentication credentials.")
    if not is_key_active(record):
        raise AuthenticationError("Invalid authentication credentials.")
    if not verify_api_key_secret(secret=secret, key_id=key_id, key_hash=record.key_hash):
        raise AuthenticationError("Invalid authentication credentials.")

    return AuthenticatedPrincipal(
        key_id=key_id,
        role=record.role,
        permissions=permissions_for_role(record.role),
        authentication_method="api_key",
        authenticated_at=utc_now_iso(),
    )


def extract_bearer_token(credentials: HTTPAuthorizationCredentials | None) -> str:
    if credentials is None or not credentials.credentials:
        raise AuthenticationError("Authentication is required.")
    if credentials.scheme.lower() != "bearer":
        raise AuthenticationError("Invalid authentication credentials.")
    return credentials.credentials


def build_get_current_principal(
    *,
    auth_config: AuthConfig,
    key_store: KeyStore,
) -> Callable[..., AuthenticatedPrincipal]:
    """Create a request-scoped principal dependency."""

    def get_current_principal(
        request: Request,
        credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    ) -> AuthenticatedPrincipal:
        if not auth_config.enabled:
            if auth_config.development_auth_mode:
                return development_principal()
            raise AuthenticationError("Authentication is required.")

        try:
            token = extract_bearer_token(credentials)
            principal = authenticate_api_key(
                auth_config=auth_config,
                key_store=key_store,
                token=token,
            )
            log_authentication_event(
                request_id=request.headers.get("X-Request-ID"),
                key_id=principal.key_id,
                role=principal.role.value,
                endpoint=request.url.path,
                method=request.method,
                outcome="success",
            )
            return principal
        except AuthenticationError:
            log_authentication_event(
                request_id=request.headers.get("X-Request-ID"),
                key_id=None,
                role=None,
                endpoint=request.url.path,
                method=request.method,
                outcome="failure",
            )
            raise

    return get_current_principal


def build_require_permission(
    permission: Permission,
    *,
    principal_getter: Callable[..., AuthenticatedPrincipal],
) -> Callable[..., AuthenticatedPrincipal]:
    return require_permission(permission, principal_getter=principal_getter)
