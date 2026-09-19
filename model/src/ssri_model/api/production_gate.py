"""Production startup fail-closed validation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ssri_model.auth.config import AuthConfig
from ssri_model.auth.exceptions import InvalidAuthConfigError


class UnsafeProductionConfigError(RuntimeError):
    """Raised when production configuration is unsafe."""


@dataclass(frozen=True)
class ProductionGateResult:
    ok: bool
    errors: tuple[str, ...]


def validate_production_environment(environ: dict[str, str] | None = None) -> ProductionGateResult:
    """Validate production safety gates without starting servers."""
    env = environ if environ is not None else dict(os.environ)
    environment = (
        env.get("SSRI_API_ENVIRONMENT")
        or env.get("SSRI_AUTH_ENVIRONMENT")
        or "development"
    ).lower()
    if environment != "production":
        return ProductionGateResult(ok=True, errors=())

    errors: list[str] = []
    auth_enabled = env.get("SSRI_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}
    if not auth_enabled:
        errors.append("SSRI_AUTH_ENABLED must be true in production")

    try:
        AuthConfig.from_env()
    except InvalidAuthConfigError as exc:
        errors.append(str(exc))

    cors = env.get("SSRI_CORS_ORIGINS") or env.get("CORS_ORIGINS") or ""
    origins = [item.strip() for item in cors.split(",") if item.strip()]
    if "*" in origins:
        errors.append("Wildcard CORS origins are not allowed in production")
    if not origins:
        errors.append("Production requires explicit SSRI_CORS_ORIGINS/CORS_ORIGINS")

    if env.get("SSRI_AUTH_DEVELOPMENT_MODE", "false").lower() in {"1", "true", "yes"}:
        errors.append("SSRI_AUTH_DEVELOPMENT_MODE must be false in production")

    key_store = env.get("SSRI_AUTH_KEY_STORE", "").strip()
    if auth_enabled and not key_store:
        errors.append("SSRI_AUTH_KEY_STORE is required when auth is enabled")

    jwt_secret = (
        env.get("SSRI_AUTH_JWT_SECRET")
        or env.get("SSRI_JWT_SECRET")
        or env.get("JWT_SECRET")
        or ""
    ).strip()
    if auth_enabled and jwt_secret:
        if len(jwt_secret) < 32:
            errors.append("JWT secret must be at least 32 characters in production")
        if jwt_secret.lower() in {"secret", "changeme", "password", "jwt_secret"}:
            errors.append("JWT secret uses an unsafe default value")

    backend = (env.get("SSRI_OBJECT_STORAGE_BACKEND") or "local").lower()
    if backend in {"s3", "minio", "r2"} and not (env.get("SSRI_OBJECT_STORAGE_BUCKET") or "").strip():
        errors.append("SSRI_OBJECT_STORAGE_BUCKET is required for S3-compatible backends")

    return ProductionGateResult(ok=not errors, errors=tuple(errors))


def assert_production_safe(environ: dict[str, str] | None = None) -> None:
    result = validate_production_environment(environ)
    if not result.ok:
        raise UnsafeProductionConfigError("; ".join(result.errors))
