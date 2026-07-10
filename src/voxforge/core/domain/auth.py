from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class OrgRole(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    MEMBER = "member"


class PrincipalType(StrEnum):
    USER = "user"
    API_KEY = "api_key"


class Principal(BaseModel):
    """Authenticated caller context resolved from JWT or API key."""

    type: PrincipalType
    user_id: UUID | None = None
    org_id: UUID
    role: OrgRole | None = None
    scopes: list[str] = Field(default_factory=list)
    api_key_id: UUID | None = None

    def has_scope(self, scope: str) -> bool:
        if scope in self.scopes:
            return True
        if self.role == OrgRole.OWNER:
            return True
        if self.role == OrgRole.ADMIN and not scope.startswith("orgs:delete"):
            return True
        role_scopes = ROLE_SCOPES.get(self.role or OrgRole.MEMBER, [])
        return scope in role_scopes


ROLE_SCOPES: dict[OrgRole, list[str]] = {
    OrgRole.OWNER: [
        "sessions:read",
        "sessions:write",
        "sessions:delete",
        "orgs:read",
        "orgs:write",
        "orgs:manage_members",
        "api_keys:read",
        "api_keys:write",
        "api_keys:delete",
        "ws:connect",
        "knowledge:read",
        "knowledge:write",
        "knowledge:delete",
        "handoffs:read",
        "handoffs:write",
        "handoffs:assign",
        "metrics:read",
    ],
    OrgRole.ADMIN: [
        "sessions:read",
        "sessions:write",
        "sessions:delete",
        "orgs:read",
        "orgs:manage_members",
        "api_keys:read",
        "api_keys:write",
        "api_keys:delete",
        "ws:connect",
        "knowledge:read",
        "knowledge:write",
        "knowledge:delete",
        "handoffs:read",
        "handoffs:write",
        "handoffs:assign",
        "metrics:read",
    ],
    OrgRole.MEMBER: [
        "sessions:read",
        "sessions:write",
        "ws:connect",
        "knowledge:read",
        "handoffs:read",
        "handoffs:write",
    ],
}

ALL_API_KEY_SCOPES: frozenset[str] = frozenset(
    scope for scopes in ROLE_SCOPES.values() for scope in scopes
)


def effective_scopes(principal: Principal) -> list[str]:
    if principal.scopes:
        return list(principal.scopes)
    if principal.role:
        return list(ROLE_SCOPES[principal.role])
    return []


def principal_has_scopes(principal: Principal, required: list[str]) -> bool:
    if not required:
        return True
    return all(principal.has_scope(scope) for scope in required)


class User(BaseModel):
    id: UUID
    email: str
    full_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


class Organization(BaseModel):
    id: UUID
    name: str
    slug: str
    created_at: datetime

    model_config = {"from_attributes": True}


class OrganizationMember(BaseModel):
    id: UUID
    org_id: UUID
    user_id: UUID
    role: OrgRole
    created_at: datetime

    model_config = {"from_attributes": True}


class ApiKey(BaseModel):
    id: UUID
    org_id: UUID
    name: str
    key_prefix: str
    scopes: list[str]
    expires_at: datetime | None
    revoked_at: datetime | None
    created_by_user_id: UUID | None
    created_at: datetime

    model_config = {"from_attributes": True}


class TokenPair(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8)
    full_name: str = Field(min_length=1, max_length=255)
    org_name: str = Field(min_length=1, max_length=255)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str
