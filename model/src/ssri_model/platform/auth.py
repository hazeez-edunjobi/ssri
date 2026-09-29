"""Resolve a Supabase user access token. Service-role keys stay on the server."""

from __future__ import annotations

import os
from dataclasses import dataclass

import httpx

from ssri_model.platform.store import PlatformError


@dataclass(frozen=True)
class PlatformIdentity:
    user_id: str
    email: str
    display_name: str


def supabase_url() -> str:
    return os.getenv("SUPABASE_URL", "").rstrip("/")


def supabase_anon_key() -> str:
    return os.getenv("SUPABASE_ANON_KEY", "")


def supabase_service_role_key() -> str:
    return os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")


def supabase_configured() -> bool:
    return bool(supabase_url() and supabase_anon_key())


def verify_supabase_access_token(token: str) -> PlatformIdentity:
    """Confirm the bearer token with Supabase Auth. Does not trust client-supplied user ids."""
    if not supabase_configured():
        raise PlatformError(
            "Supabase authentication is not configured on this server.",
            code="PLATFORM_NOT_CONFIGURED",
            status=503,
        )
    try:
        response = httpx.get(
            f"{supabase_url()}/auth/v1/user",
            headers={
                "Authorization": f"Bearer {token}",
                "apikey": supabase_anon_key(),
            },
            timeout=15.0,
        )
    except httpx.HTTPError as exc:
        raise PlatformError(
            "Could not reach the authentication service.",
            code="AUTH_UNAVAILABLE",
            status=503,
        ) from exc
    if response.status_code != 200:
        raise PlatformError(
            "Your session is invalid or has expired. Sign in again.",
            code="UNAUTHENTICATED",
            status=401,
        )
    payload = response.json()
    user_id = str(payload.get("id") or "")
    email = str(payload.get("email") or "")
    meta = payload.get("user_metadata") or {}
    display_name = str(meta.get("display_name") or email.split("@")[0])
    if not user_id:
        raise PlatformError(
            "Your session is invalid or has expired. Sign in again.",
            code="UNAUTHENTICATED",
            status=401,
        )
    return PlatformIdentity(user_id=user_id, email=email, display_name=display_name)
