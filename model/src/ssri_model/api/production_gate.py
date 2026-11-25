"""Production and staging startup fail-closed validation."""

from __future__ import annotations

import os
from dataclasses import dataclass

from ssri_model.auth.config import AuthConfig
from ssri_model.auth.exceptions import InvalidAuthConfigError


class UnsafeProductionConfigError(RuntimeError):
    """Raised when production or staging configuration is unsafe."""


@dataclass(frozen=True)
class ProductionGateResult:
    ok: bool
    errors: tuple[str, ...]
    environment: str = "development"


def _environment_name(env: dict[str, str]) -> str:
    return (
        env.get("SSRI_API_ENVIRONMENT")
        or env.get("SSRI_AUTH_ENVIRONMENT")
        or "development"
    ).lower()


def validate_staging_environment(environ: dict[str, str] | None = None) -> ProductionGateResult:
    """Subset of production gates for staging / ops qualification.

    Staging must not silently run with demo mode, development auth, or wildcard CORS.
    Full auth-enabled requirements remain production-only unless operators enable auth.
    """
    env = environ if environ is not None else dict(os.environ)
    environment = _environment_name(env)
    if environment != "staging":
        return ProductionGateResult(ok=True, errors=(), environment=environment)

    errors: list[str] = []
    cors = env.get("SSRI_CORS_ORIGINS") or env.get("CORS_ORIGINS") or ""
    origins = [item.strip() for item in cors.split(",") if item.strip()]
    if "*" in origins:
        errors.append("Wildcard CORS origins are not allowed in staging")

    if env.get("SSRI_AUTH_DEVELOPMENT_MODE", "false").lower() in {"1", "true", "yes"}:
        errors.append("SSRI_AUTH_DEVELOPMENT_MODE must be false in staging")

    if env.get("SSRI_DEMO_MODE", "false").lower() in {"1", "true", "yes"}:
        errors.append("SSRI_DEMO_MODE must be false in staging")

    auth_enabled = env.get("SSRI_AUTH_ENABLED", "false").lower() in {"1", "true", "yes"}
    if auth_enabled:
        try:
            AuthConfig.from_env()
        except InvalidAuthConfigError as exc:
            errors.append(str(exc))
        if "SSRI_AUTH_KEY_STORE" in env and not env.get("SSRI_AUTH_KEY_STORE", "").strip():
            errors.append("SSRI_AUTH_KEY_STORE is required when auth is enabled in staging")

    return ProductionGateResult(ok=not errors, errors=tuple(errors), environment=environment)


def validate_production_environment(environ: dict[str, str] | None = None) -> ProductionGateResult:
    """Validate production safety gates without starting servers."""
    env = environ if environ is not None else dict(os.environ)
    environment = _environment_name(env)
    if environment == "staging":
        return validate_staging_environment(env)
    if environment != "production":
        return ProductionGateResult(ok=True, errors=(), environment=environment)

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

    # Unset uses AuthConfig's default path. An explicit blank value is still rejected.
    if auth_enabled and "SSRI_AUTH_KEY_STORE" in env and not env.get("SSRI_AUTH_KEY_STORE", "").strip():
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
    execution_mode = (env.get("SSRI_EXECUTION_MODE") or "local").lower()
    require_durable = env.get("SSRI_REQUIRE_DURABLE_OBJECT_STORAGE", "").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }
    if backend in {"s3", "minio", "r2"}:
        from ssri_model.storage.durable import validate_object_storage_configuration

        errors.extend(validate_object_storage_configuration(env))
    if (
        backend == "local"
        and (execution_mode == "distributed" or require_durable)
    ):
        errors.append(
            "SSRI_OBJECT_STORAGE_BACKEND=local is not durable across separate "
            "API/worker hosts. Set backend to r2/s3/minio with a shared bucket, "
            "or co-locate API+worker on one host with a shared SSRI_API_OUTPUT_ROOT."
        )
    geo_backend = (env.get("SSRI_GEOLOGICAL_STORAGE_BACKEND") or "filesystem").lower()
    if geo_backend in {"r2", "s3", "minio", "object", "objects"}:
        errors.append(
            "SSRI_GEOLOGICAL_STORAGE_BACKEND object-only modes are unsupported. "
            "Keep filesystem and set SSRI_OBJECT_STORAGE_BACKEND=r2|s3|minio so "
            "catalogue trees are mirrored to durable object storage."
        )

    if env.get("SSRI_DEMO_MODE", "false").lower() in {"1", "true", "yes"}:
        errors.append("SSRI_DEMO_MODE must be false in production")

    return ProductionGateResult(ok=not errors, errors=tuple(errors), environment=environment)


def assert_production_safe(environ: dict[str, str] | None = None) -> None:
    result = validate_production_environment(environ)
    if not result.ok:
        raise UnsafeProductionConfigError("; ".join(result.errors))
