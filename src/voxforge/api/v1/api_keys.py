from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import get_auth_service, get_current_principal
from voxforge.core.domain.auth import ApiKey, Principal
from voxforge.core.exceptions import ApiKeyNotFoundError, ForbiddenError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.modules.auth.application.service import AuthService

router = APIRouter(prefix="/api-keys", tags=["api-keys"])

DEFAULT_SCOPES = ["sessions:read", "sessions:write", "ws:connect"]


class CreateApiKeyRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    scopes: list[str] = Field(default_factory=lambda: list(DEFAULT_SCOPES))
    expires_at: datetime | None = None


class ApiKeyResponse(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: str | None
    created_at: str


class CreateApiKeyResponse(ApiKeyResponse):
    raw_key: str


@router.post("", response_model=CreateApiKeyResponse, status_code=201)
async def create_api_key(
    body: CreateApiKeyRequest,
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> CreateApiKeyResponse:
    try:
        api_key, raw_key = await auth_service.create_api_key(
            org_id=principal.org_id,
            name=body.name,
            scopes=body.scopes,
            actor=principal,
            expires_at=body.expires_at,
        )
        await auth_service.commit()
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    return _to_create_response(api_key, raw_key)


@router.get("", response_model=list[ApiKeyResponse])
async def list_api_keys(
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[ApiKeyResponse]:
    try:
        keys = await auth_service.list_api_keys(principal.org_id, principal)
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    return [_to_response(k) for k in keys]


@router.delete("/{key_id}", response_model=ApiKeyResponse)
async def revoke_api_key(
    key_id: UUID,
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> ApiKeyResponse:
    try:
        revoked = await auth_service.revoke_api_key(key_id, principal)
        await auth_service.commit()
    except (ForbiddenError, ApiKeyNotFoundError) as exc:
        status = 404 if isinstance(exc, ApiKeyNotFoundError) else 403
        raise HTTPException(status_code=status, detail=exc.message) from exc
    return _to_response(revoked)


def _to_response(key: ApiKey) -> ApiKeyResponse:
    return ApiKeyResponse(
        id=key.id,
        org_id=key.org_id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=key.scopes,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        created_at=key.created_at.isoformat(),
    )


def _to_create_response(key: ApiKey, raw_key: str) -> CreateApiKeyResponse:
    return CreateApiKeyResponse(
        id=key.id,
        org_id=key.org_id,
        name=key.name,
        key_prefix=key.key_prefix,
        scopes=key.scopes,
        expires_at=key.expires_at.isoformat() if key.expires_at else None,
        created_at=key.created_at.isoformat(),
        raw_key=raw_key,
    )
