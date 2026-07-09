from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from voxforge.core.domain.mcp import MCPServerRecord, MCPServerStatus
from voxforge.core.domain.tools import ToolCallStatus, ToolDefinition, ToolResult
from voxforge.core.interfaces.mcp import MCPDiscoveryClient, MCPInvocationClient
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.tools.mcp_config import server_display_name, server_id_for

logger = get_logger(__name__)


def _tool_definitions_from_static(
    server: dict[str, Any],
    *,
    server_id: str,
    permissions: list[str],
) -> list[ToolDefinition]:
    definitions: list[ToolDefinition] = []
    for tool in server.get("tools", []):
        definitions.append(
            ToolDefinition(
                name=tool["name"],
                description=tool.get("description", ""),
                parameters=tool.get("parameters", {}),
                source="mcp",
                server_id=server_id,
                version=tool.get("version"),
                required_scopes=permissions,
            )
        )
    return definitions


def _mcp_tool_to_definition(
    tool: Any,
    *,
    server_id: str,
    permissions: list[str],
) -> ToolDefinition:
    input_schema = getattr(tool, "inputSchema", None) or {}
    return ToolDefinition(
        name=tool.name,
        description=getattr(tool, "description", "") or "",
        parameters=input_schema if isinstance(input_schema, dict) else {},
        source="mcp",
        server_id=server_id,
        version=getattr(tool, "version", None),
        required_scopes=permissions,
    )


class StdioMCPDiscoveryClient(MCPDiscoveryClient):
    async def discover(
        self, server_config: dict[str, Any]
    ) -> tuple[list[ToolDefinition], MCPServerRecord]:
        server_id = server_config.get("_server_id", server_id_for(server_config, 0))
        name = server_display_name(server_config, server_id)
        transport = server_config.get("transport", "stdio")
        permissions = list(server_config.get("permissions", []))
        capabilities = list(server_config.get("capabilities", []))
        now = datetime.now(UTC)

        record = MCPServerRecord(
            server_id=server_id,
            name=name,
            transport=transport,
            status=MCPServerStatus.UNKNOWN,
            permissions=permissions,
            capabilities=capabilities,
        )

        if transport != "stdio":
            record.status = MCPServerStatus.OFFLINE
            record.last_error = f"Unsupported MCP transport: {transport}"
            record.last_discovered_at = now
            return [], record

        command = server_config.get("command")
        if not command:
            static_tools = _tool_definitions_from_static(
                server_config, server_id=server_id, permissions=permissions
            )
            if static_tools:
                record.status = MCPServerStatus.DEGRADED
                record.tool_count = len(static_tools)
                record.discovery_source = "static"
                record.last_discovered_at = now
                record.last_error = "MCP server command not configured; using static tool metadata"
                return static_tools, record
            record.status = MCPServerStatus.OFFLINE
            record.last_error = "MCP server command not configured"
            record.last_discovered_at = now
            return [], record

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            static_tools = _tool_definitions_from_static(
                server_config, server_id=server_id, permissions=permissions
            )
            if static_tools:
                record.status = MCPServerStatus.DEGRADED
                record.tool_count = len(static_tools)
                record.discovery_source = "static"
                record.last_discovered_at = now
                record.last_error = "MCP client not installed (pip install mcp)"
                return static_tools, record
            record.status = MCPServerStatus.OFFLINE
            record.last_error = "MCP client not installed (pip install mcp)"
            record.last_discovered_at = now
            return [], record

        params = StdioServerParameters(command=command, args=server_config.get("args", []))
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.list_tools()
                    tools = [
                        _mcp_tool_to_definition(
                            tool,
                            server_id=server_id,
                            permissions=permissions,
                        )
                        for tool in result.tools
                    ]
                    record.status = MCPServerStatus.HEALTHY
                    record.tool_count = len(tools)
                    record.discovery_source = "runtime"
                    record.version = getattr(result, "version", None)
                    record.last_discovered_at = now
                    return tools, record
        except Exception as exc:
            logger.warning(
                "mcp_discovery_failed",
                server_id=server_id,
                error=str(exc),
            )
            static_tools = _tool_definitions_from_static(
                server_config, server_id=server_id, permissions=permissions
            )
            if static_tools:
                record.status = MCPServerStatus.DEGRADED
                record.tool_count = len(static_tools)
                record.discovery_source = "static"
                record.last_discovered_at = now
                record.last_error = str(exc)
                return static_tools, record
            record.status = MCPServerStatus.OFFLINE
            record.last_error = str(exc)
            record.last_discovered_at = now
            return [], record


class StdioMCPInvocationClient(MCPInvocationClient):
    async def invoke(
        self,
        server_config: dict[str, Any],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult:
        transport = server_config.get("transport", "stdio")
        if transport != "stdio":
            return ToolResult(
                tool_name=tool_name,
                output="",
                status=ToolCallStatus.ERROR,
                error=f"Unsupported MCP transport: {transport}",
            )

        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            return ToolResult(
                tool_name=tool_name,
                output="",
                status=ToolCallStatus.ERROR,
                error="MCP client not installed (pip install mcp)",
            )

        command = server_config.get("command")
        if not command:
            return ToolResult(
                tool_name=tool_name,
                output="",
                status=ToolCallStatus.ERROR,
                error="MCP server command not configured",
            )

        params = StdioServerParameters(command=command, args=server_config.get("args", []))
        try:
            async with stdio_client(params) as (read, write):
                async with ClientSession(read, write) as session:
                    await session.initialize()
                    result = await session.call_tool(tool_name, arguments)
                    text_parts = [
                        block.text
                        for block in result.content
                        if hasattr(block, "text") and block.text
                    ]
                    output = "\n".join(text_parts) if text_parts else str(result.content)
                    return ToolResult(tool_name=tool_name, output=output)
        except Exception as exc:
            logger.error("mcp_invoke_error", tool=tool_name, error=str(exc))
            return ToolResult(
                tool_name=tool_name,
                output="",
                status=ToolCallStatus.ERROR,
                error=str(exc),
            )
