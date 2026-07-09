"""Shared factory for ToolRegistry construction."""

from voxforge.config import Settings
from voxforge.infrastructure.providers.support.factory import (
    create_knowledge_base_provider,
    create_ticketing_provider,
)
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry
from voxforge.infrastructure.tools.support_tools import build_support_tools
from voxforge.modules.mcp_tool_router.application.registry import ToolRegistry


def build_support_tool_handlers(settings: Settings) -> list[object]:
    if not settings.support_tools_enabled:
        return []
    knowledge_base = create_knowledge_base_provider(settings)
    ticketing = create_ticketing_provider(settings)
    return build_support_tools(knowledge_base, ticketing)


def register_support_tool_discovery(
    settings: Settings,
    mcp_registry: MCPRuntimeRegistry,
) -> None:
    """Register support tool metadata for MCP runtime discovery (once at startup)."""
    if not settings.support_tools_enabled:
        return
    mcp_registry.register_internal_support_tools(build_support_tool_handlers(settings))


def create_tool_registry(
    settings: Settings,
    mcp_registry: MCPRuntimeRegistry | None = None,
) -> ToolRegistry:
    return ToolRegistry(
        mcp_registry=mcp_registry,
        extra_tools=build_support_tool_handlers(settings),
    )
