import base64
from datetime import UTC, datetime, timedelta

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner


def generate_idp_key_and_cert() -> tuple[object, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Test IdP")])
    now = datetime.now(UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=1))
        .sign(key, hashes.SHA256())
    )
    cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")
    return key, cert_pem


def build_signed_saml_response(
    *,
    sp_entity_id: str,
    email: str = "sso-user@example.com",
    full_name: str = "Sso User",
    groups: list[str] | None = None,
    key=None,
    cert=None,
) -> tuple[str, str]:
    if key is None or cert is None:
        key, cert_pem = generate_idp_key_and_cert()
        cert = x509.load_pem_x509_certificate(cert_pem.encode("utf-8"))
    else:
        cert_pem = cert.public_bytes(serialization.Encoding.PEM).decode("utf-8")

    groups = groups or ["support_admins"]
    now = datetime.now(UTC)
    not_before = (now - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_after = (now + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    group_xml = "".join(
        f'<saml:Attribute Name="groups"><saml:AttributeValue>{group}</saml:AttributeValue></saml:Attribute>'
        for group in groups
    )

    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<samlp:Response xmlns:samlp="urn:oasis:names:tc:SAML:2.0:protocol" xmlns:saml="urn:oasis:names:tc:SAML:2.0:assertion" ID="_response" Version="2.0">
  <saml:Assertion ID="_assertion" IssueInstant="{now.strftime("%Y-%m-%dT%H:%M:%SZ")}" Version="2.0">
    <saml:Issuer>Test IdP</saml:Issuer>
    <saml:Subject>
      <saml:NameID>fallback@example.com</saml:NameID>
    </saml:Subject>
    <saml:Conditions NotBefore="{not_before}" NotOnOrAfter="{not_after}">
      <saml:AudienceRestriction>
        <saml:Audience>{sp_entity_id}</saml:Audience>
      </saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AttributeStatement>
      <saml:Attribute Name="email">
        <saml:AttributeValue>{email}</saml:AttributeValue>
      </saml:Attribute>
      <saml:Attribute Name="displayName">
        <saml:AttributeValue>{full_name}</saml:AttributeValue>
      </saml:Attribute>
      {group_xml}
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>"""

    root = etree.fromstring(xml.encode("utf-8"))
    assertion = root.find("{urn:oasis:names:tc:SAML:2.0:assertion}Assertion")
    signed_assertion = XMLSigner().sign(assertion, key=key, cert=[cert])
    root.replace(assertion, signed_assertion)
    encoded = base64.b64encode(etree.tostring(root)).decode("utf-8")
    return cert_pem, encoded
