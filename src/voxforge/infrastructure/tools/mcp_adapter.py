"""Backward-compatible facade over MCPRuntimeRegistry."""

from typing import Any

from voxforge.core.domain.tools import ToolDefinition, ToolResult
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry


class MCPToolAdapter:
    """Deprecated: use MCPRuntimeRegistry directly."""

    def __init__(self, registry: MCPRuntimeRegistry) -> None:
        self._registry = registry

    def list_tool_definitions(self) -> list[ToolDefinition]:
        return self._registry.list_tool_definitions()

    async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        return await self._registry.invoke(name, arguments)
