import base64
import zlib
from datetime import UTC, datetime
from urllib.parse import parse_qs, urlparse
from uuid import uuid4

import pytest
from lxml import etree

from tests.helpers.saml_fixtures import build_signed_saml_response, generate_idp_key_and_cert
from voxforge.core.domain.auth import OrgRole
from voxforge.core.domain.sso import (
    SamlConnection,
    SamlConnectionStatus,
    SamlProviderType,
)
from voxforge.core.exceptions import SamlAssertionError
from voxforge.infrastructure.security.saml import (
    HTTP_REDIRECT_BINDING,
    build_authn_request_xml,
    build_sp_initiated_login_redirect,
    build_sp_metadata,
    encode_saml_redirect_binding,
    parse_saml_assertion,
    resolve_role_from_mapping,
    validate_saml_response,
)

DS_NS = "http://www.w3.org/2000/09/xmldsig#"


def _strip_signatures(signed_response: str) -> str:
    root = etree.fromstring(base64.b64decode(signed_response))
    for signature in root.findall(f".//{{{DS_NS}}}Signature"):
        parent = signature.getparent()
        if parent is not None:
            parent.remove(signature)
    return base64.b64encode(etree.tostring(root)).decode("utf-8")


def _connection(*, sp_entity_id: str = "voxforge-sp", cert_pem: str = "cert") -> SamlConnection:
    now = datetime.now(UTC)
    return SamlConnection(
        id=uuid4(),
        org_id=uuid4(),
        provider_type=SamlProviderType.OKTA,
        status=SamlConnectionStatus.ACTIVE,
        idp_entity_id="idp",
        idp_sso_url="https://idp.example.com/sso",
        idp_x509_cert=cert_pem,
        sp_entity_id=sp_entity_id,
        acs_url="https://voxforge.example.com/acs",
        default_role=OrgRole.MEMBER,
        created_at=now,
        updated_at=now,
    )


def test_parse_signed_saml_assertion():
    _, signed_response = build_signed_saml_response(sp_entity_id="voxforge-sp")
    assertion = parse_saml_assertion(signed_response)
    assert assertion.email == "sso-user@example.com"
    assert assertion.full_name == "Sso User"
    assert assertion.groups == ["support_admins"]


def test_validate_signed_saml_response():
    cert_pem, signed_response = build_signed_saml_response(sp_entity_id="voxforge-sp")
    validate_saml_response(
        signed_response,
        _connection(sp_entity_id="voxforge-sp", cert_pem=cert_pem),
        require_signature=True,
    )


def test_validate_rejects_unsigned_when_signature_required():
    cert_pem, signed_response = build_signed_saml_response(sp_entity_id="voxforge-sp")
    unsigned = _strip_signatures(signed_response)
    with pytest.raises(SamlAssertionError, match="signature is required"):
        validate_saml_response(
            unsigned,
            _connection(sp_entity_id="voxforge-sp", cert_pem=cert_pem),
            require_signature=True,
        )


def test_validate_rejects_wrong_audience():
    cert_pem, signed_response = build_signed_saml_response(sp_entity_id="voxforge-sp")
    with pytest.raises(SamlAssertionError, match="audience"):
        validate_saml_response(
            signed_response,
            _connection(sp_entity_id="other-sp", cert_pem=cert_pem),
            require_signature=True,
        )


def test_validate_rejects_invalid_signature_cert():
    _, signed_response = build_signed_saml_response(sp_entity_id="voxforge-sp")
    other_cert = generate_idp_key_and_cert()[1]
    with pytest.raises(SamlAssertionError, match="signature verification failed"):
        validate_saml_response(
            signed_response,
            _connection(sp_entity_id="voxforge-sp", cert_pem=other_cert),
            require_signature=True,
        )


def test_resolve_role_from_mapping():
    role = resolve_role_from_mapping(
        groups=["support_admins"],
        role_mapping_rules={"support_admins": "admin"},
        default_role=OrgRole.MEMBER,
    )
    assert role == OrgRole.ADMIN


def test_build_sp_metadata_contains_entity_and_acs():
    metadata = build_sp_metadata(_connection())
    assert 'entityID="voxforge-sp"' in metadata
    assert 'Location="https://voxforge.example.com/acs"' in metadata


def test_build_authn_request_xml_contains_sp_and_acs():
    connection = _connection()
    xml = build_authn_request_xml(connection, request_id="_request123")
    assert "AuthnRequest" in xml
    assert connection.sp_entity_id in xml
    assert connection.acs_url in xml
    assert connection.idp_sso_url in xml


def test_encode_saml_redirect_binding_roundtrip():
    xml = build_authn_request_xml(_connection(), request_id="_request123")
    encoded = encode_saml_redirect_binding(xml)
    decoded = zlib.decompress(base64.b64decode(encoded), -15).decode("utf-8")
    assert decoded == xml


def test_build_sp_initiated_login_redirect_url():
    connection = _connection()
    relay_state = "org:abc:connection:def"
    redirect = build_sp_initiated_login_redirect(connection, relay_state=relay_state)
    assert redirect.binding == HTTP_REDIRECT_BINDING
    assert redirect.relay_state == relay_state
    assert redirect.redirect_url.startswith(connection.idp_sso_url)
    assert "SAMLRequest=" in redirect.redirect_url
    assert "RelayState=" in redirect.redirect_url
    params = parse_qs(urlparse(redirect.redirect_url).query)
    decoded = zlib.decompress(base64.b64decode(params["SAMLRequest"][0]), -15).decode("utf-8")
    assert "AuthnRequest" in decoded
    assert connection.sp_entity_id in decoded
