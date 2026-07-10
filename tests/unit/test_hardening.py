"""Unit tests for production hardening sprint (P0)."""

from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.auth import (
    Principal,
    PrincipalType,
    effective_scopes,
    principal_has_scopes,
)
from voxforge.core.domain.tools import ToolCallStatus
from voxforge.infrastructure.knowledge.util import safe_upload_filename
from voxforge.infrastructure.security.production import collect_production_errors
from voxforge.infrastructure.tools.handoff_tools import HandoffToHumanTool
from voxforge.modules.handoff.application.replay_link import ReplayLinkService
from voxforge.modules.mcp_tool_router.application.registry import ToolRegistry
from voxforge.modules.mcp_tool_router.application.router import ToolRouter


def test_safe_upload_filename_strips_path_traversal():
    assert safe_upload_filename("../../../etc/passwd") == "passwd"
    assert safe_upload_filename("docs/report.pdf") == "report.pdf"
    assert safe_upload_filename("") == "document.txt"


def test_production_trusted_hosts_include_internal_probes():
    settings = Settings(
        app_env="production",
        trusted_hosts="voxforge.example.com",
    )
    assert settings.trusted_host_list == [
        "voxforge.example.com",
        "localhost",
        "127.0.0.1",
        "app",
    ]


def test_production_rejects_auth_disabled():
    settings = Settings(
        app_env="production",
        auth_required=False,
        jwt_secret_key="a" * 32,
        api_key_hash_pepper="b" * 32,
        trusted_hosts="demo.example.com",
        stt_provider="mock",
        llm_provider="mock",
        tts_provider="mock",
        handoff_enabled=False,
    )
    errors = collect_production_errors(settings)
    assert any("AUTH_REQUIRED" in error for error in errors)


def test_replay_link_verify_round_trip():
    settings = Settings(jwt_secret_key="test-secret-key-with-sufficient-length")
    service = ReplayLinkService(settings)
    session_id = uuid4()
    org_id = uuid4()
    handoff_id = uuid4()
    _, token = service.generate(session_id=session_id, org_id=org_id, handoff_id=handoff_id)
    assert service.verify(
        session_id=session_id,
        org_id=org_id,
        handoff_id=handoff_id,
        token=token,
    )
    assert not service.verify(
        session_id=session_id,
        org_id=org_id,
        handoff_id=handoff_id,
        token="tampered.token",
    )


@pytest.mark.asyncio
async def test_tool_router_enforces_required_scopes():
    registry = ToolRegistry(extra_tools=[HandoffToHumanTool(orchestrator=object())])  # type: ignore[arg-type]
    router = ToolRouter(registry, Settings(tools_enabled=True))
    result = await router.execute(
        "handoff_to_human",
        {"reason": "test"},
        caller_scopes=["sessions:read"],
    )
    assert result.status == ToolCallStatus.ERROR
    assert "Missing required scope" in (result.error or "")


@pytest.mark.asyncio
async def test_tool_router_allows_scoped_invocation():
    registry = ToolRegistry(extra_tools=[HandoffToHumanTool(orchestrator=object())])  # type: ignore[arg-type]
    router = ToolRouter(registry, Settings(tools_enabled=True))
    result = await router.execute(
        "calculate",
        {"expression": "1 + 1"},
        caller_scopes=["sessions:read"],
    )
    assert result.status == ToolCallStatus.SUCCESS


def test_principal_has_scopes():
    principal = Principal(
        type=PrincipalType.USER,
        org_id=uuid4(),
        scopes=["sessions:read", "handoffs:write"],
    )
    assert principal_has_scopes(principal, ["handoffs:write"])
    assert not principal_has_scopes(principal, ["knowledge:write"])


def test_effective_scopes_from_role():
    from voxforge.core.domain.auth import OrgRole

    principal = Principal(
        type=PrincipalType.USER,
        org_id=uuid4(),
        role=OrgRole.MEMBER,
    )
    scopes = effective_scopes(principal)
    assert "handoffs:write" in scopes
    assert "api_keys:write" not in scopes
