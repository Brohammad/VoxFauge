import base64
import xml.etree.ElementTree as ET
from xml.etree.ElementTree import Element

from voxforge.core.domain.auth import OrgRole
from voxforge.core.domain.sso import SamlAssertion, SamlConnection
from voxforge.core.exceptions import SamlAssertionError

SAML_NS = {
    "samlp": "urn:oasis:names:tc:SAML:2.0:protocol",
    "saml": "urn:oasis:names:tc:SAML:2.0:assertion",
}

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
    <AssertionConsumerService Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" Location="{connection.acs_url}" index="1"/>
  </SPSSODescriptor>
</EntityDescriptor>"""


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
