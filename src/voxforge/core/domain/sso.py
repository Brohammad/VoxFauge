from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field

from voxforge.core.domain.auth import OrgRole


class SamlProviderType(StrEnum):
    GENERIC = "generic"
    OKTA = "okta"
    AZURE_AD = "azure_ad"
    GOOGLE = "google"


class SamlConnectionStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    DISABLED = "disabled"


class SamlConnection(BaseModel):
    id: UUID
    org_id: UUID
    provider_type: SamlProviderType
    status: SamlConnectionStatus
    idp_entity_id: str
    idp_sso_url: str
    idp_x509_cert: str
    sp_entity_id: str
    acs_url: str
    default_role: OrgRole
    role_mapping_rules: dict = Field(default_factory=dict)
    created_by_user_id: UUID | None = None
    updated_by_user_id: UUID | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
