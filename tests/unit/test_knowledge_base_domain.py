"""Unit tests for knowledge base domain logic and citation utilities."""

from datetime import UTC, datetime
from uuid import uuid4

import pytest

from voxforge.core.domain.knowledge import (
    ChunkMetadata,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    SourceType,
)
from voxforge.modules.knowledge.application.citation import (
    build_citation,
    build_citation_label,
    compute_chunk_diff,
    format_context_snippets,
    next_version_number,
)


class TestCitationLabel:
    def test_pdf_with_page(self):
        label = build_citation_label(
            document_title="Employee Handbook",
            source_type=SourceType.PDF,
            page=14,
        )
        assert label == "[Employee Handbook p.14]"

    def test_markdown_with_heading(self):
        label = build_citation_label(
            document_title="API Docs",
            source_type=SourceType.MARKDOWN,
            heading="Authentication",
        )
        assert label == "[API Docs Authentication]"

    def test_version_suffix(self):
        label = build_citation_label(
            document_title="Policy",
            source_type=SourceType.TXT,
            version=3,
        )
        assert label == "[Policy v3]"

    def test_csv_with_heading(self):
        label = build_citation_label(
            document_title="Products",
            source_type=SourceType.CSV,
            heading="rows 100-150",
        )
        assert label == "[Products [rows 100-150]]"


@pytest.fixture
def sample_entities():
    doc_id = uuid4()
    version_id = uuid4()
    chunk_id = uuid4()
    org_id = uuid4()
    now = datetime.now(UTC)

    document = KnowledgeDocument(
        id=doc_id,
        org_id=org_id,
        collection_id=uuid4(),
        title="Refund Policy",
        source_type=SourceType.PDF,
        content_hash="abc123",
        created_at=now,
        updated_at=now,
    )
    version = KnowledgeDocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_number=2,
        content_hash="abc123",
        blob_path="org/doc/v2/policy.pdf",
        chunk_count=10,
        created_at=now,
    )
    chunk = KnowledgeChunk(
        id=chunk_id,
        org_id=org_id,
        document_version_id=version_id,
        chunk_index=5,
        content="Refunds are available within 30 days of purchase for all products. " * 15,
        content_hash="chunk_hash",
        metadata=ChunkMetadata(page=3, heading="Refund Terms"),
        created_at=now,
    )
    return document, version, chunk


class TestBuildCitation:
    def test_citation_structure(self, sample_entities):
        document, version, chunk = sample_entities
        citation = build_citation(
            chunk=chunk,
            document=document,
            version=version,
            similarity=0.8734,
        )
        assert citation.document_title == "Refund Policy"
        assert citation.version == 2
        assert citation.page == 3
        assert citation.similarity == 0.8734
        assert citation.citation_label == "[Refund Policy p.3 v2]"
        assert citation.excerpt.endswith("...")

    def test_short_excerpt_not_truncated(self, sample_entities):
        document, version, chunk = sample_entities
        chunk.content = "Short text."
        citation = build_citation(
            chunk=chunk,
            document=document,
            version=version,
            similarity=0.9,
        )
        assert citation.excerpt == "Short text."


class TestFormatContextSnippets:
    def test_formats_for_hallucination_evaluator(self, sample_entities):
        document, version, chunk = sample_entities
        citation = build_citation(
            chunk=chunk,
            document=document,
            version=version,
            similarity=0.87,
        )
        snippets = format_context_snippets([citation])
        assert len(snippets) == 1
        assert snippets[0].startswith("[Refund Policy p.3 v2]")
        assert "relevance 0.87" in snippets[0]


class TestChunkDiff:
    def test_all_new(self):
        unchanged, new, removed = compute_chunk_diff(
            {},
            [(0, "hash_a"), (1, "hash_b")],
        )
        assert unchanged == []
        assert new == [0, 1]
        assert removed == []

    def test_no_changes(self):
        unchanged, new, removed = compute_chunk_diff(
            {0: "hash_a", 1: "hash_b"},
            [(0, "hash_a"), (1, "hash_b")],
        )
        assert unchanged == [0, 1]
        assert new == []
        assert removed == []

    def test_incremental_update(self):
        unchanged, new, removed = compute_chunk_diff(
            {0: "hash_a", 1: "hash_b", 2: "hash_c"},
            [(0, "hash_a"), (1, "hash_b_changed"), (3, "hash_d")],
        )
        assert 0 in unchanged
        assert 1 in new
        assert 2 in removed
        assert 3 in new


class TestVersioning:
    def test_first_version(self):
        assert next_version_number(None) == 1

    def test_increment(self):
        assert next_version_number(5) == 6
