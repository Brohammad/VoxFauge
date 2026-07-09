import base64

import pytest

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


async def _register_user(auth_client, email: str, org_name: str) -> tuple[str, str]:
    response = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": email,
            "password": "securepass123",
            "full_name": email.split("@")[0].title(),
            "org_name": org_name,
        },
    )
    assert response.status_code == 201
    payload = response.json()
    return payload["tokens"]["access_token"], payload["org_id"]


@pytest.mark.asyncio
async def test_saml_connection_crud_scaffold(auth_client):
    token, org_id = await _register_user(auth_client, "sso-owner@example.com", "SSO Org")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = await auth_client.post(
        f"/api/v1/orgs/{org_id}/sso/saml",
        headers=headers,
        json={
            "provider_type": "okta",
            "idp_entity_id": "http://idp.example.com/metadata",
            "idp_sso_url": "https://idp.example.com/sso",
            "idp_x509_cert": "-----BEGIN CERTIFICATE-----\nFAKE\n-----END CERTIFICATE-----",
            "sp_entity_id": "voxforge-sp",
            "acs_url": "https://voxforge.example.com/api/v1/orgs/abc/sso/saml/acs",
            "default_role": "member",
            "role_mapping_rules": {"admin_group": "admin"},
        },
    )
    assert create_resp.status_code == 201
    created = create_resp.json()
    assert created["status"] == "draft"
    assert created["provider_type"] == "okta"
    connection_id = created["id"]

    list_resp = await auth_client.get(f"/api/v1/orgs/{org_id}/sso/saml", headers=headers)
    assert list_resp.status_code == 200
    assert len(list_resp.json()) == 1

    update_resp = await auth_client.patch(
        f"/api/v1/orgs/{org_id}/sso/saml/{connection_id}",
        headers=headers,
        json={"status": "active", "role_mapping_rules": {"support_admins": "admin"}},
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["status"] == "active"

    begin_login_resp = await auth_client.get(
        f"/api/v1/orgs/{org_id}/sso/saml/{connection_id}/login",
        headers=headers,
    )
    assert begin_login_resp.status_code == 200
    begin_payload = begin_login_resp.json()
    assert begin_payload["status"] == "redirect"
    assert begin_payload["connection_id"] == connection_id

    metadata_resp = await auth_client.get(
        f"/api/v1/orgs/{org_id}/sso/saml/{connection_id}/metadata",
        headers=headers,
    )
    assert metadata_resp.status_code == 200
    assert "EntityDescriptor" in metadata_resp.text

    acs_resp = await auth_client.post(
        f"/api/v1/orgs/{org_id}/sso/saml/acs",
        json={
            "saml_response": base64.b64encode(SAMPLE_SAML.encode("utf-8")).decode("utf-8"),
            "relay_state": f"org:{org_id}:connection:{connection_id}",
        },
    )
    assert acs_resp.status_code == 200
    acs_payload = acs_resp.json()
    assert acs_payload["status"] == "authenticated"
    assert acs_payload["role"] == "admin"
    assert acs_payload["tokens"]["access_token"]

    delete_resp = await auth_client.delete(
        f"/api/v1/orgs/{org_id}/sso/saml/{connection_id}",
        headers=headers,
    )
    assert delete_resp.status_code == 204

    list_after_delete = await auth_client.get(f"/api/v1/orgs/{org_id}/sso/saml", headers=headers)
    assert list_after_delete.status_code == 200
    assert list_after_delete.json() == []


@pytest.mark.asyncio
async def test_saml_connection_org_scope_protected(auth_client):
    token_one, org_one = await _register_user(auth_client, "sso-tenant1@example.com", "Org One")
    token_two, _ = await _register_user(auth_client, "sso-tenant2@example.com", "Org Two")
    headers_one = {"Authorization": f"Bearer {token_one}"}
    headers_two = {"Authorization": f"Bearer {token_two}"}

    create_resp = await auth_client.post(
        f"/api/v1/orgs/{org_one}/sso/saml",
        headers=headers_one,
        json={
            "provider_type": "generic",
            "idp_entity_id": "idp-org-one",
            "idp_sso_url": "https://org-one.example.com/sso",
            "idp_x509_cert": "fake-cert",
            "sp_entity_id": "voxforge-org-one",
            "acs_url": "https://voxforge.example.com/api/v1/orgs/org-one/sso/saml/acs",
            "default_role": "member",
        },
    )
    assert create_resp.status_code == 201

    forbidden_list = await auth_client.get(f"/api/v1/orgs/{org_one}/sso/saml", headers=headers_two)
    assert forbidden_list.status_code == 403
