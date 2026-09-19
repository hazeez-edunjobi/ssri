"""API key management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response

from ssri_model.api.dependencies import (
    get_app_state,
    get_key_manager,
    refresh_key_store,
    require_manage_auth,
)
from ssri_model.api.schemas import APIKeySummaryBody, CreateAPIKeyRequestBody, CreateAPIKeyResponseBody
from ssri_model.auth.exceptions import InvalidAuthConfigError
from ssri_model.auth.key_management import KeyStoreManager
from ssri_model.auth.models import AuthenticatedPrincipal, Role

router = APIRouter(prefix="/auth/keys", tags=["auth-keys"])


@router.post("", response_model=CreateAPIKeyResponseBody, status_code=201)
def create_api_key(
    body: CreateAPIKeyRequestBody,
    request: Request,
    manager: KeyStoreManager = Depends(get_key_manager),
    principal: AuthenticatedPrincipal = Depends(require_manage_auth),
) -> CreateAPIKeyResponseBody:
    generated = manager.create_key(
        role=Role(body.role),
        name=body.name,
        expires_at=body.expires_at,
        actor_key_id=principal.key_id,
    )
    refresh_key_store(get_app_state(request))
    return CreateAPIKeyResponseBody(
        key_id=generated.key_id,
        api_key=generated.plaintext_key,
        role=generated.record.role.value,
        name=generated.record.description,
        expires_at=generated.record.expires_at,
        created_at=generated.record.created_at,
    )


@router.get("", response_model=list[APIKeySummaryBody])
def list_api_keys(
    manager: KeyStoreManager = Depends(get_key_manager),
    _principal: AuthenticatedPrincipal = Depends(require_manage_auth),
) -> list[APIKeySummaryBody]:
    return [
        APIKeySummaryBody(
            key_id=record.key_id,
            role=record.role.value,
            enabled=record.enabled,
            name=record.description,
            expires_at=record.expires_at,
            created_at=record.created_at,
        )
        for record in manager.list_keys()
    ]


@router.get("/{key_id}", response_model=APIKeySummaryBody)
def get_api_key(
    key_id: str,
    manager: KeyStoreManager = Depends(get_key_manager),
    _principal: AuthenticatedPrincipal = Depends(require_manage_auth),
) -> APIKeySummaryBody:
    record = manager.get_key(key_id)
    if record is None:
        raise InvalidAuthConfigError("Key not found")
    return APIKeySummaryBody(
        key_id=record.key_id,
        role=record.role.value,
        enabled=record.enabled,
        name=record.description,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


@router.post("/{key_id}/disable", response_model=APIKeySummaryBody)
def disable_api_key(
    key_id: str,
    request: Request,
    manager: KeyStoreManager = Depends(get_key_manager),
    principal: AuthenticatedPrincipal = Depends(require_manage_auth),
) -> APIKeySummaryBody:
    record = manager.disable_key(key_id, actor_key_id=principal.key_id)
    refresh_key_store(get_app_state(request))
    return APIKeySummaryBody(
        key_id=record.key_id,
        role=record.role.value,
        enabled=record.enabled,
        name=record.description,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


@router.post("/{key_id}/enable", response_model=APIKeySummaryBody)
def enable_api_key(
    key_id: str,
    request: Request,
    manager: KeyStoreManager = Depends(get_key_manager),
    principal: AuthenticatedPrincipal = Depends(require_manage_auth),
) -> APIKeySummaryBody:
    record = manager.enable_key(key_id, actor_key_id=principal.key_id)
    refresh_key_store(get_app_state(request))
    return APIKeySummaryBody(
        key_id=record.key_id,
        role=record.role.value,
        enabled=record.enabled,
        name=record.description,
        expires_at=record.expires_at,
        created_at=record.created_at,
    )


@router.delete("/{key_id}", status_code=204, response_class=Response)
def delete_api_key(
    key_id: str,
    request: Request,
    manager: KeyStoreManager = Depends(get_key_manager),
    principal: AuthenticatedPrincipal = Depends(require_manage_auth),
) -> Response:
    manager.delete_key(key_id, actor_key_id=principal.key_id)
    refresh_key_store(get_app_state(request))
    return Response(status_code=204)
