from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.auth import OrgRole, Principal
from voxforge.core.domain.sso import SamlConnection, SamlConnectionStatus, SamlProviderType
from voxforge.core.exceptions import ForbiddenError
from voxforge.infrastructure.db.auth_repositories import AuditLogRepository, SamlConnectionRepository
from voxforge.modules.auth.application.service import AuthService


class SamlConnectionService:
    def __init__(self, db_session: AsyncSession) -> None:
        self._db = db_session
        self._repo = SamlConnectionRepository(db_session)
        self._audit = AuditLogRepository(db_session)

    async def list_connections(self, org_id: UUID, actor: Principal) -> list[SamlConnection]:
        self._require_org_scope(actor, org_id, "orgs:read")
        return await self._repo.list_for_org(org_id)

    async def create_connection(
        self,
        *,
        org_id: UUID,
        provider_type: SamlProviderType,
        idp_entity_id: str,
        idp_sso_url: str,
        idp_x509_cert: str,
        sp_entity_id: str,
        acs_url: str,
        default_role: OrgRole,
        role_mapping_rules: dict,
        actor: Principal,
    ) -> SamlConnection:
        self._require_org_scope(actor, org_id, "orgs:write")
        connection = await self._repo.create(
            org_id=org_id,
            provider_type=provider_type,
            status=SamlConnectionStatus.DRAFT,
            idp_entity_id=idp_entity_id,
            idp_sso_url=idp_sso_url,
            idp_x509_cert=idp_x509_cert,
            sp_entity_id=sp_entity_id,
            acs_url=acs_url,
            default_role=default_role,
            role_mapping_rules=role_mapping_rules,
            actor_user_id=actor.user_id,
        )
        await self._audit.log(
            action="sso.saml.connection_created",
            resource_type="saml_connection",
            org_id=org_id,
            user_id=actor.user_id,
            resource_id=str(connection.id),
            metadata={
                "provider_type": provider_type.value,
                "status": connection.status.value,
            },
        )
        return connection

    async def update_connection(
        self,
        *,
        org_id: UUID,
        connection_id: UUID,
        status: SamlConnectionStatus,
        role_mapping_rules: dict,
        actor: Principal,
    ) -> SamlConnection:
        self._require_org_scope(actor, org_id, "orgs:write")
        existing = await self._repo.get(connection_id)
        if existing.org_id != org_id:
            raise ForbiddenError("Access denied for this organization")
        updated = await self._repo.update(
            connection_id=connection_id,
            status=status,
            role_mapping_rules=role_mapping_rules,
            actor_user_id=actor.user_id,
        )
        await self._audit.log(
            action="sso.saml.connection_updated",
            resource_type="saml_connection",
            org_id=org_id,
            user_id=actor.user_id,
            resource_id=str(updated.id),
            metadata={"status": updated.status.value},
        )
        return updated

    async def delete_connection(self, *, org_id: UUID, connection_id: UUID, actor: Principal) -> None:
        self._require_org_scope(actor, org_id, "orgs:write")
        existing = await self._repo.get(connection_id)
        if existing.org_id != org_id:
            raise ForbiddenError("Access denied for this organization")
        await self._repo.delete(connection_id)
        await self._audit.log(
            action="sso.saml.connection_deleted",
            resource_type="saml_connection",
            org_id=org_id,
            user_id=actor.user_id,
            resource_id=str(connection_id),
        )

    async def begin_login(self, *, org_id: UUID, connection_id: UUID, actor: Principal) -> dict:
        self._require_org_scope(actor, org_id, "orgs:read")
        connection = await self._repo.get(connection_id)
        if connection.org_id != org_id:
            raise ForbiddenError("Access denied for this organization")
        return {
            "connection_id": str(connection.id),
            "sso_url": connection.idp_sso_url,
            "sp_entity_id": connection.sp_entity_id,
            "acs_url": connection.acs_url,
            "relay_state": f"org:{org_id}",
            "status": "not_implemented",
        }

    async def consume_acs(
        self,
        *,
        org_id: UUID,
        actor: Principal,
        saml_response: str,
        relay_state: str | None,
    ) -> dict:
        self._require_org_scope(actor, org_id, "orgs:read")
        await self._audit.log(
            action="sso.saml.acs_received",
            resource_type="organization",
            org_id=org_id,
            user_id=actor.user_id,
            metadata={
                "relay_state": relay_state,
                "saml_response_length": len(saml_response),
                "status": "not_implemented",
            },
        )
        return {
            "status": "not_implemented",
            "message": "SAML assertion validation and user provisioning hooks are not implemented yet",
        }

    async def commit(self) -> None:
        await self._db.commit()

    @staticmethod
    def _require_org_scope(actor: Principal, org_id: UUID, scope: str) -> None:
        if actor.org_id != org_id:
            raise ForbiddenError("Access denied for this organization")
        AuthService.require_scope(actor, scope)
