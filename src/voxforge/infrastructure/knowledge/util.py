"""Shared utilities for knowledge base ingestion."""

from __future__ import annotations

import hashlib
import re


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())


def detect_source_type(filename: str, content_type: str | None = None) -> str:
    name = filename.lower()
    if name.endswith(".pdf"):
        return "pdf"
    if name.endswith(".md") or name.endswith(".markdown"):
        return "markdown"
    if name.endswith(".html") or name.endswith(".htm"):
        return "html"
    if name.endswith(".csv"):
        return "csv"
    if name.endswith(".txt"):
        return "txt"
    if content_type:
        if "pdf" in content_type:
            return "pdf"
        if "html" in content_type:
            return "html"
        if "csv" in content_type:
            return "csv"
        if "markdown" in content_type:
            return "markdown"
    return "txt"
