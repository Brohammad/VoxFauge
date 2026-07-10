"""Unit tests for customer support tools and providers."""

import json

import pytest

from voxforge.config import Settings
from voxforge.core.domain.tools import ToolCallStatus
from voxforge.infrastructure.providers.support.mock import (
    MockKnowledgeBaseProvider,
    MockTicketingProvider,
)
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry
from voxforge.infrastructure.tools.registry_factory import (
    build_support_tool_handlers,
    create_tool_registry,
)
from voxforge.infrastructure.tools.support_tools import (
    KnowledgeBaseLookupTool,
    TicketCreateTool,
    TicketLookupTool,
)
from voxforge.modules.mcp_tool_router.application.router import ToolRouter


@pytest.fixture
def knowledge_base():
    return MockKnowledgeBaseProvider()


@pytest.fixture
def ticketing():
    return MockTicketingProvider()


@pytest.mark.asyncio
async def test_knowledge_base_lookup_returns_articles(knowledge_base):
    tool = KnowledgeBaseLookupTool(knowledge_base)
    result = await tool.invoke({"query": "refund billing"})
    payload = json.loads(result)
    assert payload["total"] >= 1
    assert any("billing" in article["category"] for article in payload["articles"])


@pytest.mark.asyncio
async def test_knowledge_base_lookup_requires_query(knowledge_base):
    tool = KnowledgeBaseLookupTool(knowledge_base)
    with pytest.raises(ValueError, match="query is required"):
        await tool.invoke({})


@pytest.mark.asyncio
async def test_ticket_lookup_by_id(ticketing):
    tool = TicketLookupTool(ticketing)
    result = await tool.invoke({"ticket_id": "TKT-1001"})
    payload = json.loads(result)
    assert payload["found"] is True
    assert payload["ticket"]["id"] == "TKT-1001"


@pytest.mark.asyncio
async def test_ticket_lookup_by_email(ticketing):
    tool = TicketLookupTool(ticketing)
    result = await tool.invoke({"customer_email": "customer@example.com"})
    payload = json.loads(result)
    assert payload["total"] >= 1


@pytest.mark.asyncio
async def test_ticket_create(ticketing):
    tool = TicketCreateTool(ticketing)
    result = await tool.invoke(
        {
            "subject": "Cannot access dashboard",
            "description": "User sees 403 after login",
            "customer_email": "new@example.com",
            "priority": "high",
        }
    )
    payload = json.loads(result)
    assert payload["created"] is True
    assert payload["ticket"]["id"].startswith("TKT-")


def test_registry_includes_support_tools():
    settings = Settings(tools_enabled=True, support_tools_enabled=True)
    registry = create_tool_registry(settings)
    names = {tool.name for tool in registry.list_definitions()}
    assert "knowledge_base_lookup" in names
    assert "ticket_lookup" in names
    assert "ticket_create" in names


@pytest.mark.asyncio
async def test_tool_router_executes_support_tool():
    settings = Settings(tools_enabled=True, support_tools_enabled=True)
    router = ToolRouter(create_tool_registry(settings), settings)
    result = await router.execute(
        "ticket_lookup",
        {"ticket_id": "TKT-1002"},
        caller_scopes=["sessions:read"],
    )
    assert result.status == ToolCallStatus.SUCCESS
    assert "TKT-1002" in result.output


def test_mcp_discovery_registers_support_server():
    settings = Settings(tools_enabled=True, support_tools_enabled=True)
    registry = MCPRuntimeRegistry(settings)
    registry.register_internal_support_tools(build_support_tool_handlers(settings))

    health = registry.get_health()
    assert health.tool_count == 3
    assert health.server_count == 1
    assert health.servers[0].server_id == "voxforge-support"

    definitions = registry.list_tool_definitions()
    assert {tool.name for tool in definitions} == {
        "knowledge_base_lookup",
        "ticket_lookup",
        "ticket_create",
    }
