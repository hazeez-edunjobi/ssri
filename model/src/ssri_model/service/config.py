"""Service configuration for SSRI operational deployment."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Mapping

from ssri_model.service.exceptions import InvalidServiceConfigError
from ssri_model.service.schemas import ServiceEnvironment


@dataclass(frozen=True)
class ServiceConfig:
    """Strongly typed configuration for future SSRI service deployment."""

    service_name: str = "ssri-inference"
    service_version: str = "0.1.0"
    environment: ServiceEnvironment = ServiceEnvironment.DEVELOPMENT
    output_root: str = "outputs/service"
    max_concurrent_jobs: int = 1
    max_input_size: int = 10_737_418_240  # 10 GiB
    allowed_feature_extensions: tuple[str, ...] = (".npy",)
    allowed_manifest_extensions: tuple[str, ...] = (".json",)
    default_inference_tile_size: int = 512
    default_inference_overlap: int = 64
    default_batch_size: int = 4
    request_timeout_seconds: int = 3600
    scientific_validation_required: bool = False
    allow_unvalidated_predictions: bool = True
    trust_client_scientific_status: bool = True

    def __post_init__(self) -> None:
        if isinstance(self.environment, str):
            object.__setattr__(self, "environment", ServiceEnvironment(self.environment))
        if not self.service_name.strip():
            raise InvalidServiceConfigError("service_name must be non-empty")
        if not self.service_version.strip():
            raise InvalidServiceConfigError("service_version must be non-empty")
        if self.max_concurrent_jobs < 1:
            raise InvalidServiceConfigError("max_concurrent_jobs must be at least 1")
        if self.max_input_size <= 0:
            raise InvalidServiceConfigError("max_input_size must be positive")
        if self.default_inference_tile_size <= 0:
            raise InvalidServiceConfigError("default_inference_tile_size must be positive")
        if self.default_inference_overlap < 0:
            raise InvalidServiceConfigError("default_inference_overlap must be non-negative")
        if self.default_inference_overlap >= self.default_inference_tile_size:
            raise InvalidServiceConfigError(
                "default_inference_overlap must be less than default_inference_tile_size"
            )
        if self.default_batch_size <= 0:
            raise InvalidServiceConfigError("default_batch_size must be positive")
        if self.request_timeout_seconds <= 0:
            raise InvalidServiceConfigError("request_timeout_seconds must be positive")
        if not self.allowed_feature_extensions:
            raise InvalidServiceConfigError("allowed_feature_extensions must not be empty")
        if not self.allowed_manifest_extensions:
            raise InvalidServiceConfigError("allowed_manifest_extensions must not be empty")
        if not self.output_root.strip():
            raise InvalidServiceConfigError("output_root must be non-empty")

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["environment"] = self.environment.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> ServiceConfig:
        environment = payload.get("environment", ServiceEnvironment.DEVELOPMENT.value)
        if isinstance(environment, ServiceEnvironment):
            env_value = environment
        else:
            env_value = ServiceEnvironment(str(environment))
        return cls(
            service_name=str(payload.get("service_name", "ssri-inference")),
            service_version=str(payload.get("service_version", "0.1.0")),
            environment=env_value,
            output_root=str(payload.get("output_root", "outputs/service")),
            max_concurrent_jobs=int(payload.get("max_concurrent_jobs", 1)),
            max_input_size=int(payload.get("max_input_size", 10_737_418_240)),
            allowed_feature_extensions=tuple(payload.get("allowed_feature_extensions", (".npy",))),
            allowed_manifest_extensions=tuple(
                payload.get("allowed_manifest_extensions", (".json",))
            ),
            default_inference_tile_size=int(payload.get("default_inference_tile_size", 512)),
            default_inference_overlap=int(payload.get("default_inference_overlap", 64)),
            default_batch_size=int(payload.get("default_batch_size", 4)),
            request_timeout_seconds=int(payload.get("request_timeout_seconds", 3600)),
            scientific_validation_required=bool(
                payload.get("scientific_validation_required", False)
            ),
            allow_unvalidated_predictions=bool(
                payload.get("allow_unvalidated_predictions", True)
            ),
            trust_client_scientific_status=bool(
                payload.get("trust_client_scientific_status", True)
            ),
        )
