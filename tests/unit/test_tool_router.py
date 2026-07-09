"""Unit tests for builtin tools and tool router."""

import pytest

from voxforge.config import Settings
from voxforge.core.domain.tools import ToolCallStatus
from voxforge.infrastructure.tools.builtin import (
    BuiltinCalculatorTool,
    BuiltinEchoTool,
    BuiltinGetTimeTool,
)
from voxforge.infrastructure.tools.registry_factory import create_tool_registry
from voxforge.modules.mcp_tool_router.application.registry import ToolRegistry
from voxforge.modules.mcp_tool_router.application.router import ToolRouter


@pytest.mark.asyncio
async def test_calculator_tool():
    tool = BuiltinCalculatorTool()
    result = await tool.invoke({"expression": "(2 + 3) * 4"})
    assert result == "20.0"


@pytest.mark.asyncio
async def test_echo_tool():
    tool = BuiltinEchoTool()
    result = await tool.invoke({"message": "hello"})
    assert result == "hello"


@pytest.mark.asyncio
async def test_get_time_tool():
    tool = BuiltinGetTimeTool()
    result = await tool.invoke({})
    assert "UTC" in result


def test_registry_lists_builtin_tools():
    registry = ToolRegistry()
    tools = registry.list_definitions()
    names = {t.name for t in tools}
    assert "calculate" in names
    assert "get_current_time" in names
    assert "echo" in names


def test_registry_lists_support_tools_when_configured():
    settings = Settings(tools_enabled=True, support_tools_enabled=True)
    registry = create_tool_registry(settings)
    names = {t.name for t in registry.list_definitions()}
    assert "knowledge_base_lookup" in names


@pytest.mark.asyncio
async def test_tool_router_executes_builtin():
    settings = Settings(tools_enabled=True)
    router = ToolRouter(ToolRegistry(), settings)
    result = await router.execute("calculate", {"expression": "1 + 2"})
    assert result.status == ToolCallStatus.SUCCESS
    assert result.output == "3.0"


@pytest.mark.asyncio
async def test_tool_router_unknown_tool():
    settings = Settings(tools_enabled=True)
    router = ToolRouter(ToolRegistry(), settings)
    result = await router.execute("nonexistent", {})
    assert result.status == ToolCallStatus.ERROR
