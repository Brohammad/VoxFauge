from datetime import UTC, datetime
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from voxforge.config import Settings
from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.knowledge import (
    ChunkSearchResult,
    Citation,
    KnowledgeChunk,
    KnowledgeSearchResponse,
    SourceType,
)
from voxforge.modules.knowledge.application.context_builder import KnowledgeContextBuilder
from voxforge.modules.memory.application.context_builder import ChatMessageLike


def _search_response(query: str, citation: Citation) -> KnowledgeSearchResponse:
    chunk = KnowledgeChunk(
        id=citation.chunk_id,
        org_id=uuid4(),
        document_version_id=uuid4(),
        chunk_index=0,
        content=citation.excerpt,
        content_hash="abc",
        created_at=datetime.now(UTC),
    )
    return KnowledgeSearchResponse(
        query=query,
        results=[ChunkSearchResult(chunk=chunk, similarity=citation.similarity, citation=citation)],
        total=1,
    )


@pytest.fixture
def settings():
    return Settings(knowledge_search_top_k=3)


@pytest.fixture
def builder(settings):
    search = AsyncMock()
    return KnowledgeContextBuilder(search, settings)


@pytest.mark.asyncio
async def test_build_context_formats_snippets(builder, settings):
    citation = Citation(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="Refund Policy",
        version=1,
        source_type=SourceType.PDF,
        page=2,
        heading=None,
        excerpt="Refunds within 30 days.",
        similarity=0.91,
        citation_label="[Refund Policy p.2]",
    )
    builder._search.search.return_value = _search_response("refund", citation)

    context = await builder.build_context(org_id=uuid4(), query="refund")

    assert context.startswith("Relevant knowledge base excerpts:")
    assert "[Refund Policy p.2]" in context
    assert "0.91" in context
    builder._search.search.assert_awaited_once()


@pytest.mark.asyncio
async def test_build_context_returns_empty_when_no_results(builder):
    builder._search.search.return_value = KnowledgeSearchResponse(query="x", results=[], total=0)

    assert await builder.build_context(org_id=uuid4(), query="x") == ""


@pytest.mark.asyncio
async def test_enrich_messages_injects_before_conversation_tail(builder):
    builder._search.search.return_value = KnowledgeSearchResponse(query="pto", results=[], total=0)
    builder.build_context = AsyncMock(
        return_value="Relevant knowledge base excerpts:\n- [Handbook]"
    )

    messages = [
        ChatMessageLike(role=MessageRole.SYSTEM, content="You are helpful."),
        ChatMessageLike(role=MessageRole.USER, content="What is PTO?"),
    ]
    enriched = await builder.enrich_messages(
        messages,
        org_id=uuid4(),
        query="What is PTO?",
    )

    assert len(enriched) == 3
    assert enriched[0].content == "You are helpful."
    assert enriched[1].role == MessageRole.SYSTEM
    assert "knowledge base excerpts" in enriched[1].content
    assert enriched[2].content == "What is PTO?"


@pytest.mark.asyncio
async def test_enrich_messages_skips_without_org(builder):
    messages = [ChatMessageLike(role=MessageRole.USER, content="Hi")]

    enriched = await builder.enrich_messages(messages, org_id=None, query="Hi")

    assert enriched == messages
    builder._search.search.assert_not_called()


@pytest.mark.asyncio
async def test_retrieve_snippets_returns_formatted_lines(builder):
    citation = Citation(
        chunk_id=uuid4(),
        document_id=uuid4(),
        document_title="Handbook",
        version=1,
        source_type=SourceType.PDF,
        page=1,
        heading=None,
        excerpt="Employees accrue 15 days.",
        similarity=0.87,
        citation_label="[Handbook p.1]",
    )
    builder._search.search.return_value = _search_response("pto", citation)

    snippets = await builder.retrieve_snippets(org_id=uuid4(), query="pto")

    assert len(snippets) == 1
    assert snippets[0].startswith("[Handbook p.1]")
