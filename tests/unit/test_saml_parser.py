import base64

import pytest

from voxforge.core.domain.auth import OrgRole
from voxforge.core.exceptions import SamlAssertionError
from voxforge.infrastructure.security.saml import (
    build_sp_metadata,
    parse_saml_assertion,
    resolve_role_from_mapping,
)
from voxforge.core.domain.sso import (
    SamlConnection,
    SamlConnectionStatus,
    SamlProviderType,
)
from datetime import UTC, datetime
from uuid import uuid4


SAMPLE_SAML = """<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion">
  <saml:Assertion>
    <saml:Subject>
      <saml:NameID>fallback@example.com</saml:NameID>
    </saml:Subject>
    <saml:AttributeStatement>
      <saml:Attribute Name="email">
        <saml:AttributeValue>sso-user@example.com</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="displayName">
        <saml:AttributeValue>Sso User</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="groups">
        <saml:AttributeValue>support_admins</saml:AttributeValue>
      </saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>"""


def test_parse_saml_assertion_from_xml():
    assertion = parse_saml_assertion(SAMPLE_SAML)
    assert assertion.email == "sso-user@example.com"
    assert assertion.full_name == "Sso User"
    assert assertion.groups == ["support_admins"]


def test_parse_saml_assertion_from_base64():
    encoded = base64.b64encode(SAMPLE_SAML.encode("utf-8")).decode("utf-8")
    assertion = parse_saml_assertion(encoded)
    assert assertion.email == "sso-user@example.com"


def test_parse_saml_assertion_missing_email_raises():
    invalid = "<samlp:Response xmlns:samlp='urn:oasis:names:tc:SAML:2.0:protocol'></samlp:Response>"
    with pytest.raises(SamlAssertionError):
        parse_saml_assertion(invalid)


def test_resolve_role_from_mapping():
    role = resolve_role_from_mapping(
        groups=["support_admins"],
        role_mapping_rules={"support_admins": "admin"},
        default_role=OrgRole.MEMBER,
    )
    assert role == OrgRole.ADMIN


def test_build_sp_metadata_contains_entity_and_acs():
    now = datetime.now(UTC)
    connection = SamlConnection(
        id=uuid4(),
        org_id=uuid4(),
        provider_type=SamlProviderType.OKTA,
        status=SamlConnectionStatus.ACTIVE,
        idp_entity_id="idp",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert="cert",
        sp_entity_id="voxforge-sp",
        acs_url="https://voxforge.example.com/acs",
        default_role=OrgRole.MEMBER,
        created_at=now,
        updated_at=now,
    )
    metadata = build_sp_metadata(connection)
    assert 'entityID="voxforge-sp"' in metadata
    assert 'Location="https://voxforge.example.com/acs"' in metadata
