"""Unit tests for InternalKnowledgeBaseProvider adapter contract.

Validates that the internal KB adapter conforms to the existing
KnowledgeBaseProvider port used by knowledge_base_lookup.
"""

import pytest

pytestmark = pytest.mark.skip(
    reason="InternalKnowledgeBaseProvider not implemented — pending ADR-005 review"
)


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
    """Tool handler works with internal provider via factory."""
    from voxforge.config import Settings
    from voxforge.infrastructure.tools.registry_factory import build_support_tool_handlers

    settings = Settings(knowledge_base_provider="internal", knowledge_enabled=True)
    handlers = build_support_tool_handlers(settings)
    kb_handler = next(h for h in handlers if h.name == "knowledge_base_lookup")
    result = await kb_handler.invoke({"query": "refund policy"})
    assert "articles" in result or "total" in result
