"""Unit tests for knowledge base document parsers."""

import pytest

from voxforge.core.domain.knowledge import SourceType
from voxforge.infrastructure.knowledge.parsers import (
    CsvParser,
    HtmlParser,
    MarkdownParser,
    TxtParser,
    get_parser,
)


@pytest.mark.asyncio
async def test_txt_parser():
    parser = TxtParser()
    doc = await parser.parse(b"Hello world text file.", filename="notes.txt")
    assert doc.source_type == SourceType.TXT
    assert "Hello world" in doc.text


@pytest.mark.asyncio
async def test_markdown_parser_extracts_heading():
    parser = MarkdownParser()
    doc = await parser.parse(b"# Refund Policy\n\nThirty day refunds.", filename="policy.md")
    assert doc.title == "Refund Policy"
    assert "Thirty day" in doc.text


@pytest.mark.asyncio
async def test_html_parser_strips_tags():
    parser = HtmlParser()
    html = b"<html><head><title>FAQ</title></head><body><p>Billing help</p></body></html>"
    doc = await parser.parse(html, filename="faq.html")
    assert "Billing help" in doc.text
    assert "<p>" not in doc.text


@pytest.mark.asyncio
async def test_csv_parser():
    parser = CsvParser()
    doc = await parser.parse(b"id,name\n1,Alice\n2,Bob", filename="users.csv")
    assert doc.source_type == SourceType.CSV
    assert "Alice" in doc.text


def test_get_parser_factory():
    assert get_parser(SourceType.TXT).source_type == SourceType.TXT
