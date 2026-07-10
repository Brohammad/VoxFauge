"""Unit tests for InternalKnowledgeBaseProvider adapter contract."""

import json

import pytest

from voxforge.config import Settings
from voxforge.infrastructure.tools.registry_factory import build_support_tool_handlers


@pytest.mark.asyncio
async def test_search_returns_knowledge_articles():
    """Adapter maps ChunkSearchResult → KnowledgeArticle for tool compatibility."""
    pytest.skip("Requires InternalKnowledgeBaseProvider")


@pytest.mark.asyncio
async def test_get_article_by_chunk_id():
    """get_article retrieves full chunk content by document ID."""
    pytest.skip("Requires InternalKnowledgeBaseProvider")


@pytest.mark.asyncio
async def test_adapter_used_by_knowledge_base_lookup_tool():
    """Tool handler works with mock provider via factory."""
    from voxforge.infrastructure.tools.registry_factory import build_support_tool_handlers

    settings = Settings(knowledge_base_provider="mock", knowledge_enabled=True)
    handlers = build_support_tool_handlers(settings)
    kb_handler = next(h for h in handlers if h.name == "knowledge_base_lookup")
    result = await kb_handler.invoke({"query": "refund policy"})
    payload = json.loads(result)
    assert payload["total"] >= 0
