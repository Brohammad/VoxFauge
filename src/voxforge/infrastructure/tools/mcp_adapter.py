"""MCP tool source — discovers tools from configured MCP servers."""

import json
from typing import Any

from voxforge.core.domain.tools import ToolCallStatus, ToolDefinition, ToolResult
from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


class MCPToolAdapter:
    """Loads tool metadata from MCP server config and invokes via MCP client when available."""

    def __init__(self, servers_config: str) -> None:
        self._servers: list[dict[str, Any]] = []
        if servers_config.strip():
            try:
                parsed = json.loads(servers_config)
                self._servers = parsed if isinstance(parsed, list) else [parsed]
            except json.JSONDecodeError:
                logger.warning("mcp_config_invalid_json")

    def list_tool_definitions(self) -> list[ToolDefinition]:
        # MCP tools are discovered at runtime when servers are connected.
        # Config-only definitions can be declared with a "tools" key per server.
        definitions: list[ToolDefinition] = []
        for server in self._servers:
            for tool in server.get("tools", []):
                definitions.append(
                    ToolDefinition(
                        name=tool["name"],
                        description=tool.get("description", ""),
                        parameters=tool.get("parameters", {}),
                        source="mcp",
                    )
                )
        return definitions

    async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        for server in self._servers:
            tool_names = {t["name"] for t in server.get("tools", [])}
            if name not in tool_names:
                continue
            return await self._invoke_mcp_server(server, name, arguments)

        return ToolResult(
            tool_name=name,
            output="",
            status=ToolCallStatus.ERROR,
            error=f"MCP tool '{name}' not found in configuration",
        )

    async def _invoke_mcp_server(
        self, server: dict[str, Any], name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        transport = server.get("transport", "stdio")
        try:
            if transport == "stdio":
                return await self._invoke_stdio(server, name, arguments)
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error=f"Unsupported MCP transport: {transport}",
            )
        except Exception as exc:
            logger.error("mcp_invoke_error", tool=name, error=str(exc))
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error=str(exc),
            )

    async def _invoke_stdio(
        self, server: dict[str, Any], name: str, arguments: dict[str, Any]
    ) -> ToolResult:
        try:
            from mcp import ClientSession, StdioServerParameters
            from mcp.client.stdio import stdio_client
        except ImportError:
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error="MCP client not installed (pip install mcp)",
            )

        command = server.get("command")
        args = server.get("args", [])
        if not command:
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error="MCP server command not configured",
            )

        params = StdioServerParameters(command=command, args=args)
        async with stdio_client(params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                result = await session.call_tool(name, arguments)
                text_parts = [
                    block.text for block in result.content if hasattr(block, "text") and block.text
                ]
                output = "\n".join(text_parts) if text_parts else str(result.content)
                return ToolResult(tool_name=name, output=output)
