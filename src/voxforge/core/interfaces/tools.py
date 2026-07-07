from typing import Any, Protocol

from voxforge.core.domain.tools import ToolDefinition, ToolResult


class ToolHandler(Protocol):
    name: str
    description: str
    parameters: dict

    async def invoke(self, arguments: dict[str, Any]) -> str: ...


class ToolProvider(Protocol):
    def list_tools(self) -> list[ToolDefinition]: ...

    async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult: ...
