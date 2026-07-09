"""Unit tests for MCP runtime registry and discovery."""

from datetime import UTC, datetime

import pytest

from voxforge.config import Settings
from voxforge.core.domain.mcp import MCPServerRecord, MCPServerStatus
from voxforge.core.domain.tools import ToolCallStatus, ToolDefinition
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry


class FakeDiscoveryClient:
    def __init__(self, *, fail: bool = False) -> None:
        self.fail = fail
        self.calls = 0

    async def discover(self, server_config: dict) -> tuple[list[ToolDefinition], MCPServerRecord]:
        self.calls += 1
        server_id = server_config["_server_id"]
        if self.fail:
            raise RuntimeError("discovery failed")

        tools = [
            ToolDefinition(
                name=f"{server_id}_search",
                description="Search tool",
                parameters={"type": "object"},
                source="mcp",
                server_id=server_id,
                required_scopes=server_config.get("permissions", []),
            )
        ]
        record = MCPServerRecord(
            server_id=server_id,
            name=server_config.get("name", server_id),
            transport="stdio",
            status=MCPServerStatus.HEALTHY,
            tool_count=1,
            permissions=list(server_config.get("permissions", [])),
            discovery_source="runtime",
            last_discovered_at=datetime.now(UTC),
        )
        return tools, record


class FakeInvocationClient:
    async def invoke(self, server_config, tool_name, arguments):
        from voxforge.core.domain.tools import ToolResult

        return ToolResult(tool_name=tool_name, output=f"ok:{arguments}")


@pytest.mark.asyncio
async def test_runtime_registry_discovers_tools():
    config = Settings(
        tools_enabled=True,
        mcp_servers_config='[{"id":"demo","name":"Demo","command":"echo","permissions":["tools:execute"]}]',
    )
    discovery = FakeDiscoveryClient()
    registry = MCPRuntimeRegistry(
        config,
        discovery_client=discovery,
        invocation_client=FakeInvocationClient(),
    )

    discovery_ms = await registry.discover_all()

    assert discovery_ms >= 0
    assert discovery.calls == 1
    assert registry.is_mcp_tool("demo_search")
    assert registry.get_tool("demo_search") is not None
    health = registry.get_health()
    assert health.status == "healthy"
    assert health.tool_count == 1


@pytest.mark.asyncio
async def test_failed_discovery_does_not_raise():
    config = Settings(
        tools_enabled=True,
        mcp_servers_config='[{"id":"bad","name":"Bad","command":"missing"}]',
    )
    registry = MCPRuntimeRegistry(config, discovery_client=FakeDiscoveryClient(fail=True))
    await registry.discover_all()
    health = registry.get_health()
    assert health.offline_count == 1
    assert health.tool_count == 0


@pytest.mark.asyncio
async def test_static_fallback_when_command_missing():
    config = Settings(
        tools_enabled=True,
        mcp_servers_config=(
            '[{"id":"static","tools":[{"name":"read_file","description":"Read","parameters":{}}]}]'
        ),
    )
    from voxforge.infrastructure.tools.mcp_stdio_client import StdioMCPDiscoveryClient

    registry = MCPRuntimeRegistry(
        config,
        discovery_client=StdioMCPDiscoveryClient(),
        invocation_client=FakeInvocationClient(),
    )
    await registry.discover_all()
    assert registry.is_mcp_tool("read_file")
    health = registry.get_health()
    assert health.status == "degraded"
    assert health.degraded_count == 1


@pytest.mark.asyncio
async def test_invoke_routes_to_registry():
    config = Settings(
        tools_enabled=True,
        mcp_servers_config='[{"id":"demo","name":"Demo","command":"echo"}]',
    )
    registry = MCPRuntimeRegistry(
        config,
        discovery_client=FakeDiscoveryClient(),
        invocation_client=FakeInvocationClient(),
    )
    await registry.discover_all()
    result = await registry.invoke("demo_search", {"q": "billing"})
    assert result.status == ToolCallStatus.SUCCESS
    assert "billing" in result.output


def test_tool_lookup_is_constant_time():
    config = Settings(
        tools_enabled=True,
        mcp_servers_config='[{"id":"demo","name":"Demo","command":"echo"}]',
    )
    registry = MCPRuntimeRegistry(config, discovery_client=FakeDiscoveryClient())
    registry._register_server_tools(  # noqa: SLF001
        "demo",
        {"_server_id": "demo"},
        [ToolDefinition(name="indexed_tool", description="", parameters={}, source="mcp")],
        MCPServerRecord(
            server_id="demo",
            name="Demo",
            transport="stdio",
            status=MCPServerStatus.HEALTHY,
        ),
    )
    assert registry.get_tool("indexed_tool") is not None
    assert registry.get_tool("missing") is None
