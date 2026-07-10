"""Citation label and version utilities for the knowledge base."""

from __future__ import annotations

from voxforge.core.domain.knowledge import (
    Citation,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    SourceType,
)


def build_citation_label(
    *,
    document_title: str,
    source_type: SourceType,
    page: int | None = None,
    heading: str | None = None,
    version: int | None = None,
) -> str:
    """Build a human-readable citation label for agent context."""
    parts: list[str] = [document_title]
    if page is not None:
        parts.append(f"p.{page}")
    elif heading:
        parts.append(heading)
    label = " ".join(parts) if len(parts) > 1 else parts[0]
    if version is not None and version > 1:
        label = f"{label} v{version}"
    if source_type == SourceType.CSV and heading:
        label = f"{document_title} [{heading}]"
    return f"[{label}]"


def build_citation(
    *,
    chunk: KnowledgeChunk,
    document: KnowledgeDocument,
    version: KnowledgeDocumentVersion,
    similarity: float,
    excerpt_max_chars: int = 200,
) -> Citation:
    """Assemble a structured citation from chunk and document metadata."""
    meta = chunk.metadata
    excerpt = chunk.content[:excerpt_max_chars]
    if len(chunk.content) > excerpt_max_chars:
        excerpt = excerpt.rstrip() + "..."

    label = build_citation_label(
        document_title=document.title,
        source_type=document.source_type,
        page=meta.page,
        heading=meta.heading,
        version=version.version_number,
    )

    return Citation(
        chunk_id=chunk.id,
        document_id=document.id,
        document_title=document.title,
        version=version.version_number,
        source_type=document.source_type,
        page=meta.page,
        heading=meta.heading,
        excerpt=excerpt,
        similarity=round(similarity, 4),
        citation_label=label,
    )


def format_context_snippets(citations: list[Citation]) -> list[str]:
    """Format citations for HallucinationEvaluator context_snippets."""
    return [f"{c.citation_label} (relevance {c.similarity:.2f}): {c.excerpt}" for c in citations]


def compute_chunk_diff(
    existing_hashes: dict[int, str],
    new_chunks: list[tuple[int, str]],
) -> tuple[list[int], list[int], list[int]]:
    """Diff chunk content hashes for incremental updates.

    Returns (unchanged_indices, new_indices, removed_indices).
    """
    new_by_index = dict(new_chunks)
    new_indices = set(new_by_index)
    old_indices = set(existing_hashes)

    unchanged = [i for i in new_indices & old_indices if existing_hashes[i] == new_by_index[i]]
    changed_or_new = sorted(new_indices - set(unchanged))
    removed = sorted(old_indices - new_indices)

    # Re-classify changed indices (same index, different hash)
    for i in new_indices & old_indices:
        if existing_hashes[i] != new_by_index[i] and i not in changed_or_new:
            changed_or_new.append(i)
    changed_or_new.sort()

    return unchanged, changed_or_new, removed


def next_version_number(current_max: int | None) -> int:
    """Return the next version number for a document."""
    if current_max is None:
        return 1
    return current_max + 1
