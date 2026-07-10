"""Deterministic mock embedding provider for tests and local dev."""

from __future__ import annotations

import hashlib
import math


class MockEmbeddingProvider:
    """Hash-seeded unit vectors — no API key required."""

    def __init__(self, *, dimensions: int = 1536) -> None:
        self._dimensions = dimensions

    def _vector_for(self, text: str) -> list[float]:
        digest = hashlib.sha256(text.encode("utf-8")).digest()
        values: list[float] = []
        for i in range(self._dimensions):
            byte = digest[i % len(digest)]
            values.append((byte / 255.0) * 2 - 1)
        norm = math.sqrt(sum(v * v for v in values)) or 1.0
        return [v / norm for v in values]

    async def embed(self, text: str) -> list[float]:
        return self._vector_for(text)

    async def embed_batch(self, texts: list[str]) -> list[list[float]]:
        return [self._vector_for(text) for text in texts]
