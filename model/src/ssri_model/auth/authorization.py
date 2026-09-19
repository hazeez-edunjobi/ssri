"""Role-based authorization helpers."""

from __future__ import annotations

from collections.abc import Callable

from fastapi import Depends

from ssri_model.auth.exceptions import AuthorizationError
from ssri_model.auth.models import AuthenticatedPrincipal, Permission, Role

_ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.VIEWER: frozenset(
        {
            Permission.READ_STATUS,
            Permission.READ_METADATA,
        }
    ),
    Role.OPERATOR: frozenset(
        {
            Permission.READ_STATUS,
            Permission.READ_METADATA,
            Permission.RUN_INFERENCE,
            Permission.RUN_BATCH,
        }
    ),
    Role.ADMIN: frozenset(
        {
            Permission.READ_STATUS,
            Permission.READ_METADATA,
            Permission.RUN_INFERENCE,
            Permission.RUN_BATCH,
            Permission.MANAGE_AUTH,
        }
    ),
}


def permissions_for_role(role: Role) -> frozenset[Permission]:
    return _ROLE_PERMISSIONS[role]


def has_permission(principal: AuthenticatedPrincipal, permission: Permission) -> bool:
    return permission in principal.permissions


def require_permission(
    permission: Permission,
    *,
    principal_getter: Callable[..., AuthenticatedPrincipal],
) -> Callable[..., AuthenticatedPrincipal]:
    """Build a FastAPI dependency that enforces a permission."""

    def _dependency(
        principal: AuthenticatedPrincipal = Depends(principal_getter),
    ) -> AuthenticatedPrincipal:
        if not has_permission(principal, permission):
            raise AuthorizationError(
                "The authenticated principal does not have permission to perform this operation."
            )
        return principal

    return _dependency
