from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.auth import ApiKey, Organization, OrganizationMember, OrgRole, User
from voxforge.core.exceptions import (
    ApiKeyNotFoundError,
    OrganizationNotFoundError,
    UserNotFoundError,
)
from voxforge.infrastructure.db.models import (
    ApiKeyModel,
    AuditLogModel,
    OrganizationMemberModel,
    OrganizationModel,
    UserModel,
)
from voxforge.infrastructure.security.tokens import slugify


class UserRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, email: str, hashed_password: str, full_name: str) -> User:
        model = UserModel(email=email, hashed_password=hashed_password, full_name=full_name)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_by_email(self, email: str) -> User | None:
        stmt = select(UserModel).where(UserModel.email == email)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get(self, user_id: UUID) -> User:
        model = await self._session.get(UserModel, user_id)
        if model is None:
            raise UserNotFoundError(str(user_id))
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: UserModel) -> User:
        return User(
            id=model.id,
            email=model.email,
            full_name=model.full_name,
            is_active=model.is_active,
            created_at=model.created_at,
        )


class OrganizationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, *, name: str, slug: str | None = None) -> Organization:
        base_slug = slug or slugify(name)
        unique_slug = await self._unique_slug(base_slug)
        model = OrganizationModel(name=name, slug=unique_slug)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get(self, org_id: UUID) -> Organization:
        model = await self._session.get(OrganizationModel, org_id)
        if model is None:
            raise OrganizationNotFoundError(str(org_id))
        return self._to_entity(model)

    async def list_for_user(self, user_id: UUID) -> list[Organization]:
        stmt = (
            select(OrganizationModel)
            .join(OrganizationMemberModel)
            .where(OrganizationMemberModel.user_id == user_id)
            .order_by(OrganizationModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def _unique_slug(self, base: str) -> str:
        slug = base
        counter = 1
        while True:
            stmt = select(OrganizationModel).where(OrganizationModel.slug == slug)
            result = await self._session.execute(stmt)
            if result.scalar_one_or_none() is None:
                return slug
            counter += 1
            slug = f"{base}-{counter}"

    @staticmethod
    def _to_entity(model: OrganizationModel) -> Organization:
        return Organization(
            id=model.id,
            name=model.name,
            slug=model.slug,
            created_at=model.created_at,
        )


class OrganizationMemberRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def add_member(
        self, *, org_id: UUID, user_id: UUID, role: OrgRole = OrgRole.MEMBER
    ) -> OrganizationMember:
        model = OrganizationMemberModel(org_id=org_id, user_id=user_id, role=role)
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get_membership(self, *, org_id: UUID, user_id: UUID) -> OrganizationMember | None:
        stmt = select(OrganizationMemberModel).where(
            OrganizationMemberModel.org_id == org_id,
            OrganizationMemberModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def list_members(self, org_id: UUID) -> list[OrganizationMember]:
        stmt = (
            select(OrganizationMemberModel)
            .where(OrganizationMemberModel.org_id == org_id)
            .order_by(OrganizationMemberModel.created_at)
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def remove_member(self, *, org_id: UUID, user_id: UUID) -> None:
        stmt = select(OrganizationMemberModel).where(
            OrganizationMemberModel.org_id == org_id,
            OrganizationMemberModel.user_id == user_id,
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            await self._session.delete(model)

    @staticmethod
    def _to_entity(model: OrganizationMemberModel) -> OrganizationMember:
        return OrganizationMember(
            id=model.id,
            org_id=model.org_id,
            user_id=model.user_id,
            role=OrgRole(model.role),
            created_at=model.created_at,
        )


class ApiKeyRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        org_id: UUID,
        name: str,
        key_prefix: str,
        key_hash: str,
        scopes: list[str],
        created_by_user_id: UUID | None,
        expires_at: datetime | None = None,
    ) -> ApiKey:
        model = ApiKeyModel(
            org_id=org_id,
            name=name,
            key_prefix=key_prefix,
            key_hash=key_hash,
            scopes=scopes,
            created_by_user_id=created_by_user_id,
            expires_at=expires_at,
        )
        self._session.add(model)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    async def get(self, key_id: UUID) -> ApiKey:
        model = await self._session.get(ApiKeyModel, key_id)
        if model is None:
            raise ApiKeyNotFoundError(str(key_id))
        return self._to_entity(model)

    async def list_for_org(self, org_id: UUID) -> list[ApiKey]:
        stmt = (
            select(ApiKeyModel)
            .where(ApiKeyModel.org_id == org_id, ApiKeyModel.revoked_at.is_(None))
            .order_by(ApiKeyModel.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return [self._to_entity(m) for m in result.scalars().all()]

    async def find_by_prefix(self, key_prefix: str) -> list[ApiKeyModel]:
        stmt = select(ApiKeyModel).where(
            ApiKeyModel.key_prefix == key_prefix,
            ApiKeyModel.revoked_at.is_(None),
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def revoke(self, key_id: UUID) -> ApiKey:
        model = await self._session.get(ApiKeyModel, key_id)
        if model is None:
            raise ApiKeyNotFoundError(str(key_id))
        model.revoked_at = datetime.now(UTC)
        await self._session.flush()
        await self._session.refresh(model)
        return self._to_entity(model)

    @staticmethod
    def _to_entity(model: ApiKeyModel) -> ApiKey:
        return ApiKey(
            id=model.id,
            org_id=model.org_id,
            name=model.name,
            key_prefix=model.key_prefix,
            scopes=model.scopes or [],
            expires_at=model.expires_at,
            revoked_at=model.revoked_at,
            created_by_user_id=model.created_by_user_id,
            created_at=model.created_at,
        )


class AuditLogRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def log(
        self,
        *,
        action: str,
        resource_type: str,
        org_id: UUID | None = None,
        user_id: UUID | None = None,
        resource_id: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        model = AuditLogModel(
            org_id=org_id,
            user_id=user_id,
            action=action,
            resource_type=resource_type,
            resource_id=resource_id,
            metadata_=metadata or {},
        )
        self._session.add(model)
