"""Authentication configuration."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Mapping

from ssri_model.auth.exceptions import InvalidAuthConfigError
from ssri_model.service.validation import reject_path_traversal


@dataclass(frozen=True)
class AuthConfig:
    """Configuration for SSRI API authentication."""

    enabled: bool = False
    environment: str = "development"
    key_store_path: str = "auth/keys.json"
    development_auth_mode: bool = True
    require_auth_in_production: bool = True

    def __post_init__(self) -> None:
        if not self.key_store_path.strip():
            raise InvalidAuthConfigError("key_store_path must be non-empty")
        reject_path_traversal(self.key_store_path, field_name="key_store_path")
        if self.require_auth_in_production and self.environment == "production" and not self.enabled:
            raise InvalidAuthConfigError(
                "Authentication cannot be disabled in production environment"
            )
        if (
            self.environment == "production"
            and self.enabled
            and self.development_auth_mode
        ):
            raise InvalidAuthConfigError(
                "development_auth_mode cannot be enabled in production"
            )
        if self.enabled and self.environment == "production" and not Path(self.key_store_path).name:
            raise InvalidAuthConfigError("Production authentication requires a key store path")

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> AuthConfig:
        return cls(
            enabled=bool(payload.get("enabled", False)),
            environment=str(payload.get("environment", "development")),
            key_store_path=str(payload.get("key_store_path", "auth/keys.json")),
            development_auth_mode=bool(payload.get("development_auth_mode", True)),
            require_auth_in_production=bool(payload.get("require_auth_in_production", True)),
        )

    @classmethod
    def from_env(cls, *, prefix: str = "SSRI_AUTH_") -> AuthConfig:
        environment = os.getenv("SSRI_API_ENVIRONMENT", os.getenv(f"{prefix}ENVIRONMENT", "development"))
        is_production = environment == "production"
        default_dev_mode = "false" if is_production else "true"
        return cls(
            enabled=os.getenv(f"{prefix}ENABLED", "false").lower() in {"1", "true", "yes"},
            environment=environment,
            key_store_path=os.getenv(f"{prefix}KEY_STORE", "auth/keys.json"),
            development_auth_mode=os.getenv(f"{prefix}DEVELOPMENT_MODE", default_dev_mode).lower()
            not in {"0", "false", "no"},
            require_auth_in_production=os.getenv(f"{prefix}REQUIRE_IN_PRODUCTION", "true").lower()
            not in {"0", "false", "no"},
        )
