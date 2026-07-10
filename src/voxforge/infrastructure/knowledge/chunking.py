"""Text chunking strategies for knowledge base ingestion."""

from __future__ import annotations

from voxforge.core.domain.knowledge import (
    ChunkingConfig,
    ChunkMetadata,
    ParsedDocument,
    RawChunk,
    SourceType,
)
from voxforge.core.interfaces.knowledge import ChunkingStrategy


class RecursiveChunker:
    async def chunk(
        self,
        document: ParsedDocument,
        *,
        config: ChunkingConfig,
    ) -> list[RawChunk]:
        if document.source_type == SourceType.CSV:
            return self._chunk_csv(document, config)
        if document.source_type == SourceType.PDF and config.strategy == "page":
            return self._chunk_pages(document)
        return self._chunk_recursive(document.text, document, config)

    def _chunk_recursive(
        self,
        text: str,
        document: ParsedDocument,
        config: ChunkingConfig,
    ) -> list[RawChunk]:
        if not text:
            return []
        size = max(config.chunk_size, 64)
        overlap = min(config.chunk_overlap, size // 2)
        chunks: list[RawChunk] = []
        start = 0
        index = 0
        while start < len(text):
            end = min(start + size, len(text))
            if end < len(text):
                split_at = text.rfind(" ", start, end)
                if split_at > start + size // 2:
                    end = split_at
            content = text[start:end].strip()
            if content:
                chunks.append(
                    RawChunk(
                        content=content,
                        chunk_index=index,
                        metadata=ChunkMetadata(
                            chunk_index=index,
                            source_type=document.source_type,
                            heading=document.headings[0] if document.headings else None,
                        ),
                        token_count=max(len(content) // 4, 1),
                    )
                )
                index += 1
            if end >= len(text):
                break
            start = max(end - overlap, start + 1)
        return chunks

    def _chunk_pages(self, document: ParsedDocument) -> list[RawChunk]:
        chunks: list[RawChunk] = []
        for i, page_text in enumerate(document.pages):
            if not page_text.strip():
                continue
            chunks.append(
                RawChunk(
                    content=page_text,
                    chunk_index=len(chunks),
                    metadata=ChunkMetadata(
                        chunk_index=len(chunks),
                        page=i + 1,
                        source_type=SourceType.PDF,
                    ),
                    token_count=max(len(page_text) // 4, 1),
                )
            )
        return chunks

    def _chunk_csv(self, document: ParsedDocument, config: ChunkingConfig) -> list[RawChunk]:
        lines = document.text.splitlines()
        if not lines:
            return []
        header = lines[0]
        data_lines = lines[1:]
        rows_per = max(config.rows_per_chunk, 1)
        chunks: list[RawChunk] = []
        for i in range(0, len(data_lines), rows_per):
            block = data_lines[i : i + rows_per]
            if config.include_header:
                content = header + "\n" + "\n".join(block)
            else:
                content = "\n".join(block)
            row_start = i + 1
            row_end = min(i + rows_per, len(data_lines))
            chunks.append(
                RawChunk(
                    content=content.strip(),
                    chunk_index=len(chunks),
                    metadata=ChunkMetadata(
                        chunk_index=len(chunks),
                        source_type=SourceType.CSV,
                        heading=f"rows {row_start}-{row_end}",
                        row_start=row_start,
                        row_end=row_end,
                    ),
                    token_count=max(len(content) // 4, 1),
                )
            )
        return chunks


def get_chunker() -> ChunkingStrategy:
    return RecursiveChunker()
