"""Document parsers for enterprise knowledge base formats."""

from __future__ import annotations

import csv
import io
import re
from html.parser import HTMLParser

from voxforge.core.domain.knowledge import ParsedDocument, SourceType
from voxforge.core.interfaces.knowledge import DocumentParser
from voxforge.infrastructure.knowledge.util import normalize_text


class TxtParser:
    source_type = SourceType.TXT

    async def parse(self, content: bytes, *, filename: str | None = None) -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        title = (filename or "document").rsplit(".", 1)[0]
        return ParsedDocument(
            title=title,
            text=normalize_text(text),
            source_type=SourceType.TXT,
        )


class CsvParser:
    source_type = SourceType.CSV

    async def parse(self, content: bytes, *, filename: str | None = None) -> ParsedDocument:
        raw = content.decode("utf-8", errors="replace")
        reader = csv.reader(io.StringIO(raw))
        rows = list(reader)
        if not rows:
            return ParsedDocument(
                title=(filename or "data").rsplit(".", 1)[0],
                text="",
                source_type=SourceType.CSV,
            )
        header = rows[0]
        lines = [", ".join(header)]
        for row in rows[1:]:
            lines.append(", ".join(row))
        text = "\n".join(lines)
        return ParsedDocument(
            title=(filename or "data").rsplit(".", 1)[0],
            text=text,
            source_type=SourceType.CSV,
            metadata={"header": header, "row_count": max(len(rows) - 1, 0)},
        )


class MarkdownParser:
    source_type = SourceType.MARKDOWN

    async def parse(self, content: bytes, *, filename: str | None = None) -> ParsedDocument:
        text = content.decode("utf-8", errors="replace")
        headings = re.findall(r"^#{1,6}\s+(.+)$", text, flags=re.MULTILINE)
        title = headings[0] if headings else (filename or "document").rsplit(".", 1)[0]
        return ParsedDocument(
            title=title.strip(),
            text=normalize_text(text),
            source_type=SourceType.MARKDOWN,
            headings=[h.strip() for h in headings],
        )


class _TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self._parts: list[str] = []
        self._skip = False

    def handle_starttag(self, tag: str, attrs) -> None:
        if tag in {"script", "style"}:
            self._skip = True

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style"}:
            self._skip = False

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self._parts.append(data.strip())

    @property
    def text(self) -> str:
        return normalize_text(" ".join(self._parts))


class HtmlParser:
    source_type = SourceType.HTML

    async def parse(self, content: bytes, *, filename: str | None = None) -> ParsedDocument:
        html = content.decode("utf-8", errors="replace")
        title_match = re.search(r"<title[^>]*>(.*?)</title>", html, flags=re.IGNORECASE | re.DOTALL)
        extractor = _TextExtractor()
        extractor.feed(html)
        title = (
            normalize_text(title_match.group(1))
            if title_match
            else (filename or "document").rsplit(".", 1)[0]
        )
        return ParsedDocument(
            title=title,
            text=extractor.text,
            source_type=SourceType.HTML,
        )


class PdfParser:
    source_type = SourceType.PDF

    async def parse(self, content: bytes, *, filename: str | None = None) -> ParsedDocument:
        try:
            from pypdf import PdfReader
        except ImportError as exc:
            raise RuntimeError("pypdf is required for PDF parsing") from exc

        reader = PdfReader(io.BytesIO(content))
        pages: list[str] = []
        for page in reader.pages:
            pages.append(normalize_text(page.extract_text() or ""))
        text = "\n\n".join(p for p in pages if p)
        title = (filename or "document").rsplit(".", 1)[0]
        if reader.metadata and reader.metadata.title:
            title = str(reader.metadata.title)
        return ParsedDocument(
            title=title,
            text=text,
            source_type=SourceType.PDF,
            pages=pages,
        )


def get_parser(source_type: SourceType) -> DocumentParser:
    mapping: dict[SourceType, DocumentParser] = {
        SourceType.TXT: TxtParser(),
        SourceType.CSV: CsvParser(),
        SourceType.MARKDOWN: MarkdownParser(),
        SourceType.HTML: HtmlParser(),
        SourceType.PDF: PdfParser(),
    }
    parser = mapping.get(source_type)
    if parser is None:
        raise ValueError(f"Unsupported source type: {source_type}")
    return parser
