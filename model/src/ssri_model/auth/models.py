"""Authentication domain models."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping


class Role(str, Enum):
    VIEWER = "viewer"
    OPERATOR = "operator"
    ADMIN = "admin"


class Permission(str, Enum):
    READ_STATUS = "read_status"
    READ_METADATA = "read_metadata"
    RUN_INFERENCE = "run_inference"
    RUN_BATCH = "run_batch"
    MANAGE_AUTH = "manage_auth"


@dataclass(frozen=True)
class APIKeyRecord:
    """Persisted API key metadata (never stores plaintext secrets)."""

    key_id: str
    key_hash: str
    role: Role
    enabled: bool = True
    created_at: str = ""
    expires_at: str | None = None
    description: str = ""

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["role"] = self.role.value
        return payload

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> APIKeyRecord:
        role_value = payload.get("role", Role.VIEWER.value)
        role = Role(str(role_value)) if not isinstance(role_value, Role) else role_value
        return cls(
            key_id=str(payload["key_id"]),
            key_hash=str(payload["key_hash"]),
            role=role,
            enabled=bool(payload.get("enabled", True)),
            created_at=str(payload.get("created_at", "")),
            expires_at=payload.get("expires_at"),
            description=str(payload.get("description", "")),
        )


@dataclass(frozen=True)
class GeneratedAPIKey:
    """Result of secure API key generation."""

    key_id: str
    plaintext_key: str
    record: APIKeyRecord


@dataclass(frozen=True)
class AuthenticatedPrincipal:
    """Authenticated request principal."""

    key_id: str
    role: Role
    permissions: frozenset[Permission]
    authentication_method: str
    authenticated_at: str

    def to_audit_dict(self) -> dict[str, str]:
        return {
            "key_id": self.key_id,
            "role": self.role.value,
            "authentication_method": self.authentication_method,
        }
