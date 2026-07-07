from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.api.dependencies import get_auth_service, get_current_principal, require_scope
from voxforge.core.domain.auth import Organization, OrgRole, Principal
from voxforge.core.exceptions import ForbiddenError, OrganizationNotFoundError
from voxforge.infrastructure.db.session import get_db_session
from voxforge.modules.auth.application.service import AuthService

router = APIRouter(prefix="/orgs", tags=["organizations"])


class CreateOrgRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)


class OrgResponse(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: str

    @classmethod
    def from_entity(cls, org: Organization) -> "OrgResponse":
        return cls(
            id=org.id,
            name=org.name,
            slug=org.slug,
            created_at=org.created_at.isoformat(),
        )


class AddMemberRequest(BaseModel):
    user_id: UUID
    role: OrgRole = OrgRole.MEMBER


class MemberResponse(BaseModel):
    id: UUID
    org_id: UUID
    user_id: UUID
    role: str
    created_at: str


@router.post("", response_model=OrgResponse, status_code=201)
async def create_org(
    body: CreateOrgRequest,
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> OrgResponse:
    if principal.user_id is None:
        raise HTTPException(status_code=400, detail="API keys cannot create organizations")
    org = await auth_service.create_org(name=body.name, user_id=principal.user_id)
    await auth_service.commit()
    return OrgResponse.from_entity(org)


@router.get("", response_model=list[OrgResponse])
async def list_orgs(
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[OrgResponse]:
    if principal.user_id is None:
        raise HTTPException(status_code=400, detail="API keys cannot list organizations")
    orgs = await auth_service.list_orgs(principal.user_id)
    return [OrgResponse.from_entity(o) for o in orgs]


@router.get("/{org_id}", response_model=OrgResponse)
async def get_org(
    org_id: UUID,
    principal: Principal = Depends(require_scope("orgs:read")),
    auth_service: AuthService = Depends(get_auth_service),
) -> OrgResponse:
    if principal.org_id != org_id:
        raise HTTPException(status_code=403, detail="Access denied for this organization")
    try:
        org = await auth_service.get_org(org_id)
    except OrganizationNotFoundError:
        raise HTTPException(status_code=404, detail="Organization not found") from None
    return OrgResponse.from_entity(org)


@router.get("/{org_id}/members", response_model=list[MemberResponse])
async def list_members(
    org_id: UUID,
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
) -> list[MemberResponse]:
    try:
        members = await auth_service.list_members(org_id, principal)
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    return [
        MemberResponse(
            id=m.id,
            org_id=m.org_id,
            user_id=m.user_id,
            role=m.role.value,
            created_at=m.created_at.isoformat(),
        )
        for m in members
    ]


@router.post("/{org_id}/members", response_model=MemberResponse, status_code=201)
async def add_member(
    org_id: UUID,
    body: AddMemberRequest,
    principal: Principal = Depends(get_current_principal),
    auth_service: AuthService = Depends(get_auth_service),
    db: AsyncSession = Depends(get_db_session),
) -> MemberResponse:
    try:
        member = await auth_service.add_member(
            org_id=org_id, user_id=body.user_id, role=body.role, actor=principal
        )
        await auth_service.commit()
    except ForbiddenError as exc:
        raise HTTPException(status_code=403, detail=exc.message) from exc
    return MemberResponse(
        id=member.id,
        org_id=member.org_id,
        user_id=member.user_id,
        role=member.role.value,
        created_at=member.created_at.isoformat(),
    )
