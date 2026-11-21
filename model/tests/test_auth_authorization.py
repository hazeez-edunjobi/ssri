"""Tests for role-based authorization."""

from __future__ import annotations

from ssri_model.auth.authorization import has_permission, permissions_for_role
from ssri_model.auth.models import AuthenticatedPrincipal, Permission, Role


def _principal(role: Role) -> AuthenticatedPrincipal:
    return AuthenticatedPrincipal(
        key_id="test-key",
        role=role,
        permissions=permissions_for_role(role),
        authentication_method="api_key",
        authenticated_at="2026-01-01T00:00:00+00:00",
    )


def test_viewer_permissions() -> None:
    principal = _principal(Role.VIEWER)
    assert has_permission(principal, Permission.READ_STATUS)
    assert has_permission(principal, Permission.READ_METADATA)
    assert not has_permission(principal, Permission.RUN_ASSESS)
    assert not has_permission(principal, Permission.RUN_INFERENCE)
    assert not has_permission(principal, Permission.MANAGE_GEOLOGICAL)


def test_user_has_assess_but_not_operator_powers() -> None:
    principal = _principal(Role.USER)
    assert has_permission(principal, Permission.RUN_ASSESS)
    assert has_permission(principal, Permission.READ_STATUS)
    assert not has_permission(principal, Permission.RUN_INFERENCE)
    assert not has_permission(principal, Permission.RUN_BATCH)
    assert not has_permission(principal, Permission.MANAGE_GEOLOGICAL)
    assert not has_permission(principal, Permission.MANAGE_AUTH)


def test_operator_permissions() -> None:
    principal = _principal(Role.OPERATOR)
    assert has_permission(principal, Permission.RUN_ASSESS)
    assert has_permission(principal, Permission.RUN_INFERENCE)
    assert has_permission(principal, Permission.RUN_BATCH)
    assert has_permission(principal, Permission.MANAGE_GEOLOGICAL)
    assert not has_permission(principal, Permission.MANAGE_AUTH)


def test_admin_includes_operator_permissions() -> None:
    principal = _principal(Role.ADMIN)
    assert has_permission(principal, Permission.RUN_ASSESS)
    assert has_permission(principal, Permission.RUN_INFERENCE)
    assert has_permission(principal, Permission.MANAGE_AUTH)
    assert has_permission(principal, Permission.MANAGE_GEOLOGICAL)
