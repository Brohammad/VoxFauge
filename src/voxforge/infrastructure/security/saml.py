import base64
import secrets
import xml.etree.ElementTree as ET
import zlib
from datetime import UTC, datetime, timedelta
from urllib.parse import quote_plus, urlencode, urlparse, urlunparse
from xml.etree.ElementTree import Element

from cryptography.x509 import load_pem_x509_certificate
from lxml import etree
from signxml import XMLVerifier
from signxml.exceptions import InvalidSignature

from voxforge.core.domain.auth import OrgRole
from voxforge.core.domain.sso import SamlAssertion, SamlConnection, SamlLoginRedirect
from voxforge.core.exceptions import SamlAssertionError

SAML_NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
}
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
HTTP_REDIRECT_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-Redirect"
HTTP_POST_BINDING = "urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST"

EMAIL_ATTRIBUTE_NAMES = {
    "email",
    "emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
}
NAME_ATTRIBUTE_NAMES = {
    "name",
    "displayname",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/givenname",
}
GROUP_ATTRIBUTE_NAMES = {
    "groups",
    "group",
    "memberof",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/groups",
}


def normalize_saml_payload(saml_response: str) -> str:
    payload = saml_response.strip()
    if payload.startswith("<"):
        return payload
    try:
        decoded = base64.b64decode(payload, validate=True)
    except Exception as exc:
        raise SamlAssertionError("SAML response must be XML or base64-encoded XML") from exc
    return decoded.decode("utf-8")


def normalize_x509_cert(cert_pem: str) -> str:
    cert = cert_pem.strip()
    if "BEGIN CERTIFICATE" in cert:
        return cert
    body = "".join(cert.split())
    wrapped = "\n".join(body[i : i + 64] for i in range(0, len(body), 64))
    return f"-----BEGIN CERTIFICATE-----\n{wrapped}\n-----END CERTIFICATE-----"


def validate_saml_response(
    saml_response: str,
    connection: SamlConnection,
    *,
    require_signature: bool,
    clock_skew_seconds: int = 120,
) -> None:
    xml = normalize_saml_payload(saml_response)
    try:
        root = etree.fromstring(xml.encode("utf-8"))
    except etree.XMLSyntaxError as exc:
        raise SamlAssertionError("Invalid SAML XML payload") from exc

    assertion = root.find(".//saml:Assertion", namespaces=SAML_NS)
    if assertion is None:
        raise SamlAssertionError("SAML assertion not found in response")

    _validate_audience(assertion, connection.sp_entity_id)
    _validate_conditions(assertion, clock_skew_seconds=clock_skew_seconds)

    if require_signature:
        if not _has_xml_signature(root):
            raise SamlAssertionError("SAML response signature is required")
        _verify_signature(xml, connection.idp_x509_cert)


def parse_saml_assertion(saml_response: str) -> SamlAssertion:
    xml = normalize_saml_payload(saml_response)
    try:
        root = ET.fromstring(xml)
    except ET.ParseError as exc:
        raise SamlAssertionError("Invalid SAML XML payload") from exc

    assertion = root.find(".//saml:Assertion", SAML_NS)
    if assertion is None:
        raise SamlAssertionError("SAML assertion not found in response")

    email = _first_attribute_value(assertion, EMAIL_ATTRIBUTE_NAMES)
    if not email:
        name_id = assertion.find("saml:Subject/saml:NameID", SAML_NS)
        if name_id is not None and name_id.text and "@" in name_id.text:
            email = name_id.text.strip()

    if not email:
        raise SamlAssertionError("SAML assertion missing email attribute")

    full_name = _first_attribute_value(assertion, NAME_ATTRIBUTE_NAMES) or email.split("@")[0]
    groups = _attribute_values(assertion, GROUP_ATTRIBUTE_NAMES)

    return SamlAssertion(email=email.lower(), full_name=full_name, groups=groups)


def resolve_role_from_mapping(
    *,
    groups: list[str],
    role_mapping_rules: dict,
    default_role: OrgRole,
) -> OrgRole:
    normalized_groups = {group.lower() for group in groups}
    for group_name, mapped_role in role_mapping_rules.items():
        if group_name.lower() in normalized_groups:
            try:
                return OrgRole(str(mapped_role))
            except ValueError:
                continue
    return default_role


def build_sp_metadata(connection: SamlConnection) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<EntityDescriptor xmlns="urn:oasis:names:tc:SAML:2.0:metadata" entityID="{connection.sp_entity_id}">
  <SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">
    <NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</NameIDFormat>
    <AssertionConsumerService Binding="{HTTP_POST_BINDING}" Location="{connection.acs_url}" index="1"/>
  </SPSSODescriptor>
</EntityDescriptor>"""


def build_authn_request_xml(
    connection: SamlConnection,
    *,
    request_id: str,
    issue_instant: datetime | None = None,
) -> str:
    issued_at = (issue_instant or datetime.now(UTC)).strftime("%Y-%m-%dT%H:%M:%SZ")
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:AuthnRequest xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="{request_id}" Version="2.0" IssueInstant="{issued_at}" Destination="{connection.idp_sso_url}" AssertionConsumerServiceURL="{connection.acs_url}" ProtocolBinding="{HTTP_POST_BINDING}">
  <saml:Issuer>{connection.sp_entity_id}</saml:Issuer>
  <samlp:NameIDPolicy Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress" AllowCreate="true"/>
</samlp:AuthnRequest>"""


def encode_saml_redirect_binding(message: str) -> str:
    compressor = zlib.compressobj(level=9, method=zlib.DEFLATED, wbits=-15)
    compressed = compressor.compress(message.encode("utf-8")) + compressor.flush()
    return base64.b64encode(compressed).decode("ascii")


def build_sp_initiated_login_redirect(
    connection: SamlConnection,
    *,
    relay_state: str,
    request_id: str | None = None,
) -> SamlLoginRedirect:
    authn_request_id = request_id or f"_{secrets.token_hex(16)}"
    authn_request_xml = build_authn_request_xml(connection, request_id=authn_request_id)
    encoded_request = encode_saml_redirect_binding(authn_request_xml)
    query = urlencode({"SAMLRequest": encoded_request, "RelayState": relay_state}, quote_via=quote_plus)
    redirect_url = _append_query(connection.idp_sso_url, query)
    return SamlLoginRedirect(
        connection_id=connection.id,
        sso_url=connection.idp_sso_url,
        redirect_url=redirect_url,
        relay_state=relay_state,
        binding=HTTP_REDIRECT_BINDING,
        saml_request=encoded_request,
    )


def _append_query(url: str, query: str) -> str:
    parsed = urlparse(url)
    merged_query = f"{parsed.query}&{query}" if parsed.query else query
    return urlunparse(parsed._replace(query=merged_query))


def _verify_signature(xml: str, idp_x509_cert: str) -> None:
    try:
        certificate = load_pem_x509_certificate(normalize_x509_cert(idp_x509_cert).encode("utf-8"))
        XMLVerifier().verify(xml.encode("utf-8"), x509_cert=certificate)
    except InvalidSignature as exc:
        raise SamlAssertionError("SAML response signature verification failed") from exc
    except ValueError as exc:
        raise SamlAssertionError("Invalid IdP X509 certificate") from exc


def _has_xml_signature(root: etree._Element) -> bool:
    return root.find(f".//{{{DS_NS}}}Signature") is not None


def _validate_audience(assertion: etree._Element, sp_entity_id: str) -> None:
    audiences = assertion.findall(".//saml:Audience", namespaces=SAML_NS)
    if not audiences:
        raise SamlAssertionError("SAML assertion missing audience restriction")
    if not any(audience.text == sp_entity_id for audience in audiences if audience.text):
        raise SamlAssertionError("SAML assertion audience does not match service provider")


def _validate_conditions(assertion: etree._Element, *, clock_skew_seconds: int) -> None:
    conditions = assertion.find("saml:Conditions", namespaces=SAML_NS)
    if conditions is None:
        raise SamlAssertionError("SAML assertion missing conditions")

    now = datetime.now(UTC)
    skew = timedelta(seconds=clock_skew_seconds)
    not_before = _parse_saml_instant(conditions.get("NotBefore"))
    not_on_or_after = _parse_saml_instant(conditions.get("NotOnOrAfter"))

    if not_before and now + skew < not_before:
        raise SamlAssertionError("SAML assertion is not yet valid")
    if not_on_or_after and now - skew > not_on_or_after:
        raise SamlAssertionError("SAML assertion has expired")


def _parse_saml_instant(value: str | None) -> datetime | None:
    if not value:
        return None
    normalized = value.replace("Z", "+00:00")
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as exc:
        raise SamlAssertionError("Invalid SAML condition timestamp") from exc
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=UTC)
    return parsed.astimezone(UTC)


def _first_attribute_value(assertion: Element, names: set[str]) -> str | None:
    for value in _attribute_values(assertion, names):
        return value
    return None


def _attribute_values(assertion: Element, names: set[str]) -> list[str]:
    values: list[str] = []
    for attribute in assertion.findall(".//saml:Attribute", SAML_NS):
        attribute_name = (attribute.get("Name") or "").lower()
        friendly_name = (attribute.get("FriendlyName") or "").lower()
        if attribute_name not in names and friendly_name not in names:
            continue
        for value_node in attribute.findall("saml:AttributeValue", SAML_NS):
            if value_node.text:
                values.append(value_node.text.strip())
    return values
