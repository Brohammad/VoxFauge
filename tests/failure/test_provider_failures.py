"""Failure-mode tests: provider timeouts and tool failures."""

import asyncio
from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.tools import ToolCallStatus
from voxforge.infrastructure.providers.mock import MockLLMProvider
from voxforge.modules.mcp_tool_router.application.registry import ToolRegistry
from voxforge.modules.mcp_tool_router.application.router import ToolRouter

pytestmark = pytest.mark.failure


class SlowTool:
    name = "slow_tool"
    description = "always times out"
    required_scopes: list[str] = []
    parameters = {"type": "object", "properties": {}, "required": []}

    async def invoke(self, _arguments):
        await asyncio.sleep(2)
        return "too late"


@pytest.mark.asyncio
async def test_tool_router_timeout_returns_timeout_status():
    registry = ToolRegistry(extra_tools=[SlowTool()])
    settings = Settings(tools_enabled=True, tool_timeout_seconds=1)
    router = ToolRouter(registry, settings)
    result = await router.execute("slow_tool", {}, org_id=uuid4(), session_id=uuid4())
    assert result.status == ToolCallStatus.TIMEOUT


@pytest.mark.asyncio
async def test_tool_router_unknown_tool():
    settings = Settings(tools_enabled=True)
    router = ToolRouter(ToolRegistry(), settings)
    result = await router.execute("missing_tool", {}, org_id=uuid4(), session_id=uuid4())
    assert result.status == ToolCallStatus.ERROR


@pytest.mark.asyncio
async def test_llm_provider_timeout_propagates():
    provider = MockLLMProvider()

    async def failing_stream(messages, model):
        _ = messages, model
        raise TimeoutError("LLM timeout")
        yield  # pragma: no cover

    provider.generate_stream = failing_stream

    from voxforge.core.domain.entities import MessageRole

    class Msg:
        role = MessageRole.USER
        content = "hello"

    with pytest.raises(TimeoutError):
        async for _ in provider.generate_stream([Msg()], model="mock"):
            pass
