from typing import Any

from langchain_core.tools import StructuredTool

from voxforge.core.domain.tools import ToolDefinition, ToolResult
from voxforge.infrastructure.tools.builtin import BUILTIN_TOOLS
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry


class ToolRegistry:
    """Registry of callable tools from builtin and MCP sources."""

    def __init__(self, mcp_registry: MCPRuntimeRegistry | None = None) -> None:
        self._handlers: dict[str, Any] = {}
        self._mcp_registry = mcp_registry
        self._register_builtins()

    def _register_builtins(self) -> None:
        for tool in BUILTIN_TOOLS:
            self._handlers[tool.name] = tool

    def list_definitions(self) -> list[ToolDefinition]:
        definitions = [
            ToolDefinition(
                name=handler.name,
                description=handler.description,
                parameters=handler.parameters,
                source="builtin",
            )
            for handler in self._handlers.values()
        ]
        if self._mcp_registry is not None:
            definitions.extend(self._mcp_registry.list_tool_definitions())
        return definitions

    def get_handler(self, name: str) -> Any | None:
        return self._handlers.get(name)

    def is_mcp_tool(self, name: str) -> bool:
        if self._mcp_registry is None:
            return False
        return self._mcp_registry.is_mcp_tool(name)

    async def invoke_mcp(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        if self._mcp_registry is None:
            raise ValueError("MCP registry not configured")
        return await self._mcp_registry.invoke(name, arguments)

    def get_langchain_tools(self) -> list[StructuredTool]:
        tools: list[StructuredTool] = []
        for handler in self._handlers.values():

            async def _invoke(*, _handler=handler, **kwargs: Any) -> str:
                return await _handler.invoke(kwargs)

            tools.append(
                StructuredTool(
                    name=handler.name,
                    description=handler.description,
                    coroutine=_invoke,
                )
            )
        return tools
