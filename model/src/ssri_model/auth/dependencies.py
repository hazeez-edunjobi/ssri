"""FastAPI authentication dependencies."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from datetime import datetime, timezone
from typing import Any

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from ssri_model.auth.audit import log_authentication_event
from ssri_model.auth.authorization import permissions_for_role, require_permission
from ssri_model.auth.config import AuthConfig
from ssri_model.auth.credentials import API_KEY_PREFIX, KeyStore, is_key_active, parse_api_key
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


_PLATFORM_ROLE_TO_AUTH: dict[str, Role] = {
    "user": Role.USER,
    "admin": Role.ADMIN,
    # Explicit operator/viewer only for tests / API-key-adjacent session maps.
    "operator": Role.OPERATOR,
    "viewer": Role.VIEWER,
}


def role_from_platform_role(role_name: str) -> Role:
    """Map platform profile role → auth Role. Unknown values fail closed."""
    normalized = (role_name or "").strip().lower()
    role = _PLATFORM_ROLE_TO_AUTH.get(normalized)
    if role is None:
        raise AuthenticationError("Invalid authentication credentials.")
    return role


def _principal_for_supabase_user(*, user_id: str, role: Role) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        key_id=str(user_id),
        role=role,
        permissions=permissions_for_role(role),
        authentication_method="supabase",
        authenticated_at=utc_now_iso(),
    )


def _role_from_profile_store(user_id: str, *, email: str, display_name: str) -> Role:
    """Load profiles.role for the verified user. Fail closed without a store."""
    from ssri_model.platform.supabase_store import supabase_store_from_env

    store = supabase_store_from_env()
    if store is None:
        raise AuthenticationError("Invalid authentication credentials.")
    profile = store.get_profile(user_id)
    if profile is None:
        profile = store.upsert_profile(
            user_id=user_id,
            email=email,
            display_name=display_name or email.split("@")[0] or user_id,
            role="user",
        )
    return role_from_platform_role(profile.role)


def authenticate_supabase_bearer(
    token: str,
    *,
    platform_tokens: Mapping[str, Any] | None = None,
) -> AuthenticatedPrincipal:
    """Authenticate a Supabase (or test) access token as a product principal.

    Signed-in ``user`` profiles receive ``Role.USER`` (``RUN_ASSESS`` only among
    write-ish permissions). They are **not** promoted to OPERATOR. Administrators
    keep ``Role.ADMIN``. API keys remain the machine-to-machine path with
    independent RBAC.
    """
    tokens = platform_tokens or {}
    if token in tokens:
        user_id, _email, role_name = tokens[token]
        role = role_from_platform_role(str(role_name))
        return _principal_for_supabase_user(user_id=str(user_id), role=role)

    from ssri_model.platform.auth import supabase_configured, verify_supabase_access_token
    from ssri_model.platform.store import PlatformError

    if not supabase_configured():
        raise AuthenticationError("Invalid authentication credentials.")
    try:
        identity = verify_supabase_access_token(token)
        role = _role_from_profile_store(
            identity.user_id,
            email=identity.email,
            display_name=identity.display_name,
        )
    except PlatformError as exc:
        if int(getattr(exc, "status", 401) or 401) >= 500:
            raise AuthenticationError(
                "Authentication service is unavailable."
            ) from exc
        raise AuthenticationError("Invalid authentication credentials.") from exc

    return _principal_for_supabase_user(user_id=identity.user_id, role=role)


def authenticate_bearer_token(
    *,
    auth_config: AuthConfig,
    key_store: KeyStore,
    token: str,
    platform_tokens: Mapping[str, Any] | None = None,
) -> AuthenticatedPrincipal:
    """Resolve Authorization Bearer to a principal (API key or Supabase session)."""
    if token.startswith(f"{API_KEY_PREFIX}_"):
        return authenticate_api_key(
            auth_config=auth_config,
            key_store=key_store,
            token=token,
        )
    return authenticate_supabase_bearer(token, platform_tokens=platform_tokens)


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
            platform_tokens = getattr(request.app.state, "platform_tokens", None)
            principal = authenticate_bearer_token(
                auth_config=auth_config,
                key_store=key_store,
                token=token,
                platform_tokens=platform_tokens,
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
