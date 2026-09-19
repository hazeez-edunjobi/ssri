"""API configuration for SSRI FastAPI service."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass, field
from typing import Any, Mapping

from ssri_model.service.config import ServiceConfig
from ssri_model.service.exceptions import InvalidServiceConfigError
from ssri_model.service.validation import validate_service_config

from ssri_model.auth.config import AuthConfig

from ssri_model.api.operational_config import OperationalConfig
from ssri_model.infrastructure.config import InfrastructureConfig


def _env_flag(name: str, default: bool = False) -> bool:
    """Parse common boolean environment representations."""
    raw = os.getenv(name)
    if raw is None or not str(raw).strip():
        return default
    return str(raw).strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class APIConfig:
    """Configuration for the SSRI HTTP API."""

    host: str = "0.0.0.0"
    port: int = 8000
    api_prefix: str = "/api/v1"
    docs_enabled: bool = True
    max_batch_jobs: int = 100
    max_request_body_bytes: int = 1_048_576
    demo_mode: bool = False
    service_config: ServiceConfig = field(default_factory=ServiceConfig)
    auth_config: AuthConfig = field(default_factory=AuthConfig)
    operational_config: OperationalConfig = field(default_factory=OperationalConfig)
    infrastructure_config: InfrastructureConfig = field(default_factory=InfrastructureConfig)

    def __post_init__(self) -> None:
        if self.port <= 0:
            raise InvalidServiceConfigError("port must be positive")
        if not self.api_prefix.startswith("/"):
            raise InvalidServiceConfigError("api_prefix must start with '/'")
        if self.max_batch_jobs < 1:
            raise InvalidServiceConfigError("max_batch_jobs must be at least 1")
        if self.max_request_body_bytes <= 0:
            raise InvalidServiceConfigError("max_request_body_bytes must be positive")
        validate_service_config(self.service_config)
        auth_environment = self.auth_config.environment
        if auth_environment != self.service_config.environment.value:
            object.__setattr__(
                self,
                "auth_config",
                AuthConfig.from_dict(
                    {
                        **self.auth_config.to_dict(),
                        "environment": self.service_config.environment.value,
                    }
                ),
            )

    @property
    def service_name(self) -> str:
        return self.service_config.service_name

    @property
    def service_version(self) -> str:
        return self.service_config.service_version

    @property
    def output_root(self) -> str:
        return self.service_config.output_root

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["service_config"] = self.service_config.to_dict()
        payload["auth_config"] = self.auth_config.to_dict()
        payload["operational_config"] = self.operational_config.to_dict()
        payload["infrastructure_config"] = self.infrastructure_config.to_dict()
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> APIConfig:
        service_payload = payload.get("service_config", {})
        service_config = (
            service_payload
            if isinstance(service_payload, ServiceConfig)
            else ServiceConfig.from_dict(service_payload)
        )
        auth_payload = payload.get("auth_config", {})
        auth_config = (
            auth_payload
            if isinstance(auth_payload, AuthConfig)
            else AuthConfig.from_dict(auth_payload)
        )
        operational_payload = payload.get("operational_config", {})
        operational_config = (
            operational_payload
            if isinstance(operational_payload, OperationalConfig)
            else OperationalConfig.from_dict(operational_payload)
        )
        infrastructure_payload = payload.get("infrastructure_config", {})
        infrastructure_config = (
            infrastructure_payload
            if isinstance(infrastructure_payload, InfrastructureConfig)
            else InfrastructureConfig.from_dict(infrastructure_payload)
        )
        return cls(
            host=str(payload.get("host", "0.0.0.0")),
            port=int(payload.get("port", 8000)),
            api_prefix=str(payload.get("api_prefix", "/api/v1")),
            docs_enabled=bool(payload.get("docs_enabled", True)),
            max_batch_jobs=int(payload.get("max_batch_jobs", 100)),
            max_request_body_bytes=int(payload.get("max_request_body_bytes", 1_048_576)),
            demo_mode=bool(payload.get("demo_mode", False)),
            service_config=service_config,
            auth_config=auth_config,
            operational_config=operational_config,
            infrastructure_config=infrastructure_config,
        )

    @classmethod
    def from_env(cls, *, prefix: str = "SSRI_API_") -> APIConfig:
        """Build API configuration from environment variables."""
        service_config = ServiceConfig.from_dict(
            {
                "service_name": os.getenv(f"{prefix}SERVICE_NAME", "ssri-inference"),
                "service_version": os.getenv(f"{prefix}SERVICE_VERSION", "0.1.0"),
                "environment": os.getenv(f"{prefix}ENVIRONMENT", "development"),
                "output_root": os.getenv(f"{prefix}OUTPUT_ROOT", "outputs/service"),
                "scientific_validation_required": os.getenv(
                    f"{prefix}SCIENTIFIC_VALIDATION_REQUIRED", "false"
                ).lower()
                in {"1", "true", "yes"},
                "allow_unvalidated_predictions": os.getenv(
                    f"{prefix}ALLOW_UNVALIDATED_PREDICTIONS", "true"
                ).lower()
                not in {"0", "false", "no"},
                "trust_client_scientific_status": os.getenv(
                    "SSRI_TRUST_CLIENT_SCIENTIFIC_STATUS",
                    "false"
                    if os.getenv(f"{prefix}ENVIRONMENT", "development").lower()
                    == "production"
                    else "true",
                ).lower()
                in {"1", "true", "yes"},
            }
        )
        auth_config = AuthConfig.from_env()
        auth_config = AuthConfig.from_dict(
            {
                **auth_config.to_dict(),
                "environment": service_config.environment.value,
            }
        )
        infrastructure_config = InfrastructureConfig.from_env(prefix="SSRI_")
        is_production = service_config.environment.value == "production"
        rate_limit_default = "true" if is_production else "false"
        operational_config = OperationalConfig.from_dict(
            {
                "rate_limit_enabled": os.getenv(
                    "SSRI_RATE_LIMIT_ENABLED", rate_limit_default
                ).lower()
                in {"1", "true", "yes"},
                "worker_count": int(os.getenv("SSRI_WORKER_COUNT", "2")),
            }
        )
        return cls(
            host=os.getenv(f"{prefix}HOST", "0.0.0.0"),
            port=int(os.getenv(f"{prefix}PORT", "8000")),
            api_prefix=os.getenv(f"{prefix}PREFIX", "/api/v1"),
            docs_enabled=os.getenv(f"{prefix}DOCS_ENABLED", "true").lower()
            not in {"0", "false", "no"},
            max_batch_jobs=int(os.getenv(f"{prefix}MAX_BATCH_JOBS", "100")),
            demo_mode=_env_flag("SSRI_DEMO_MODE", default=False),
            service_config=service_config,
            auth_config=auth_config,
            operational_config=operational_config,
            infrastructure_config=infrastructure_config,
        )
