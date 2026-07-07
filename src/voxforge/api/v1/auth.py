from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import get_auth_service, get_current_principal
from voxforge.core.domain.auth import (
    LoginRequest,
    Principal,
    RefreshRequest,
    RegisterRequest,
    TokenPair,
)
from voxforge.core.exceptions import InvalidCredentialsError, UnauthorizedError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.modules.auth.application.service import AuthService

router = APIRouter(prefix="/auth", tags=["auth"])


class RegisterResponse(BaseModel):
    user_id: UUID
    org_id: UUID
    email: str
    full_name: str
    org_name: str
    tokens: TokenPair


class UserResponse(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool


class MeResponse(BaseModel):
    user: UserResponse
    org_id: UUID
    role: str | None = None
    principal_type: str


@router.post("/register", response_model=RegisterResponse, status_code=201)
async def register(
    body: RegisterRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> RegisterResponse:
    try:
        user, org, tokens = await auth_service.register(body)
        await auth_service.commit()
    except InvalidCredentialsError as exc:
        raise HTTPException(status_code=400, detail=exc.message) from exc

    return RegisterResponse(
        user_id=user.id,
        org_id=org.id,
        email=user.email,
        full_name=user.full_name,
        org_name=org.name,
        tokens=tokens,
    )


@router.post("/login", response_model=TokenPair)
async def login(
    body: LoginRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    try:
        tokens = await auth_service.login(body)
        await auth_service.commit()
    except (InvalidCredentialsError, UnauthorizedError) as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    return tokens


@router.post("/refresh", response_model=TokenPair)
async def refresh(
    body: RefreshRequest,
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> TokenPair:
    try:
        tokens = await auth_service.refresh(body.refresh_token)
        await auth_service.commit()
    except UnauthorizedError as exc:
        raise HTTPException(status_code=401, detail=exc.message) from exc
    return tokens


@router.get("/me", response_model=MeResponse)
async def me(
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> MeResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=400, detail="API key principals have no user profile")
    user = await auth_service.get_user(principal.user_id)
    return MeResponse(
        user=UserResponse(
            id=user.id,
            email=user.email,
            full_name=user.full_name,
            is_active=user.is_active,
        ),
        org_id=principal.org_id,
        role=principal.role.value if principal.role else None,
        principal_type=principal.type.value,
    )
