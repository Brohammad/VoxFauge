from typing import Any, Protocol

from voxforge.core.domain.mcp import MCPServerRecord
from voxforge.core.domain.tools import ToolDefinition, ToolResult


class MCPDiscoveryClient(Protocol):
    """Discovers tools and server metadata from a configured MCP server."""

    async def discover(
        self, server_config: dict[str, Any]
    ) -> tuple[list[ToolDefinition], MCPServerRecord]: ...


class MCPInvocationClient(Protocol):
    """Invokes a tool on a configured MCP server."""

    async def invoke(
        self,
        server_config: dict[str, Any],
        tool_name: str,
        arguments: dict[str, Any],
    ) -> ToolResult: ...
