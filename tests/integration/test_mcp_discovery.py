"""Integration tests for MCP runtime discovery API."""

import json

import pytest

from voxforge.config import Settings, get_settings
from voxforge.core.domain.mcp import MCPServerRecord, MCPServerStatus
from voxforge.core.domain.tools import ToolDefinition
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry
from voxforge.main import app


class StubDiscovery:
    async def discover(self, server_config: dict):
        server_id = server_config["_server_id"]
        tools = [
            ToolDefinition(
                name="integration_search",
                description="Integration search tool",
                parameters={"type": "object"},
                source="mcp",
                server_id=server_id,
            )
        ]
        record = MCPServerRecord(
            server_id=server_id,
            name="Integration Server",
            transport="stdio",
            status=MCPServerStatus.HEALTHY,
            tool_count=1,
            discovery_source="runtime",
        )
        return tools, record


@pytest.fixture
def mcp_registry_override():
    config = Settings(
        tools_enabled=True,
        mcp_servers_config=json.dumps(
            [{"id": "integration", "name": "Integration", "command": "echo"}]
        ),
        mcp_startup_discover=False,
    )
    registry = MCPRuntimeRegistry(config, discovery_client=StubDiscovery())
    app.state.mcp_registry = registry
    yield registry
    app.state.mcp_registry = None
    get_settings.cache_clear()


@pytest.mark.asyncio
async def test_mcp_health_endpoint(auth_client, mcp_registry_override):
    await mcp_registry_override.discover_all()

    token_resp = await auth_client.post(
        "/api/v1/auth/register",
        json={
            "email": "mcp-health@example.com",
            "password": "securepass123",
            "full_name": "MCP User",
            "org_name": "MCP Org",
        },
    )
    token = token_resp.json()["tokens"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    health_resp = await auth_client.get("/api/v1/tools/mcp/health", headers=headers)
    assert health_resp.status_code == 200
    payload = health_resp.json()
    assert payload["status"] == "healthy"
    assert payload["tool_count"] == 1
    assert payload["healthy_count"] == 1

    servers_resp = await auth_client.get("/api/v1/tools/mcp/servers", headers=headers)
    assert servers_resp.status_code == 200
    servers = servers_resp.json()["servers"]
    assert len(servers) == 1
    assert servers[0]["server_id"] == "integration"

    tools_resp = await auth_client.get("/api/v1/tools", headers=headers)
    assert tools_resp.status_code == 200
    tool_names = {t["name"] for t in tools_resp.json()["tools"]}
    assert "integration_search" in tool_names
    assert "calculate" in tool_names
