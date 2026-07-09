#!/usr/bin/env python3
"""Reproducible benchmark for enterprise knowledge base ingestion and search.

Measures ingest pipeline stages, semantic search latency, and citation assembly
using mock providers (no API keys required).

This script is a scaffold — full benchmarks activate after Phase 3 implementation.
See docs/benchmarks/knowledge-base.md.

Usage:
    python scripts/benchmark_knowledge_base.py
    python scripts/benchmark_knowledge_base.py --iterations 20 --json
    python scripts/benchmark_knowledge_base.py --search-only --json
"""

from __future__ import annotations

import argparse
import json
import platform
import sys
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from voxforge.core.domain.knowledge import (  # noqa: E402
    ChunkMetadata,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    SourceType,
)
from voxforge.modules.knowledge.application.citation import (  # noqa: E402
    build_citation,
    format_context_snippets,
)


@dataclass
class LatencyStats:
    mean: float
    p50: float
    p95: float
    min: float
    max: float


@dataclass
class BenchmarkResult:
    timestamp: str
    environment: dict
    status: str
    citation_assembly_ms: LatencyStats | None = None
    note: str = ""


def _percentile_stats(samples: list[float]) -> LatencyStats:
    ordered = sorted(samples)
    count = len(ordered)

    def pct(p: float) -> float:
        if count == 1:
            return ordered[0]
        idx = min(int(round((p / 100) * (count - 1))), count - 1)
        return ordered[idx]

    return LatencyStats(
        mean=round(sum(ordered) / count, 3),
        p50=round(pct(50), 3),
        p95=round(pct(95), 3),
        min=round(ordered[0], 3),
        max=round(ordered[-1], 3),
    )


def _benchmark_citation_assembly(iterations: int) -> LatencyStats:
    """Benchmark citation assembly (available now — no DB required)."""
    import time

    now = datetime.now(UTC)
    doc_id = uuid4()
    version_id = uuid4()
    org_id = uuid4()

    document = KnowledgeDocument(
        id=doc_id,
        org_id=org_id,
        collection_id=uuid4(),
        title="Benchmark Document",
        source_type=SourceType.PDF,
        content_hash="hash",
        created_at=now,
        updated_at=now,
    )
    version = KnowledgeDocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_number=1,
        content_hash="hash",
        blob_path="bench/doc.pdf",
        created_at=now,
    )
    chunk = KnowledgeChunk(
        id=uuid4(),
        org_id=org_id,
        document_version_id=version_id,
        chunk_index=0,
        content="Sample chunk content for benchmark citation assembly. " * 10,
        content_hash="chunk_hash",
        metadata=ChunkMetadata(page=1),
        created_at=now,
    )

    samples: list[float] = []
    for _ in range(iterations):
        start = time.perf_counter()
        citation = build_citation(
            chunk=chunk,
            document=document,
            version=version,
            similarity=0.85,
        )
        format_context_snippets([citation])
        samples.append((time.perf_counter() - start) * 1000)

    return _percentile_stats(samples)


def run_benchmark(*, iterations: int, search_only: bool) -> BenchmarkResult:
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }

    citation_stats = _benchmark_citation_assembly(iterations)

    note_parts = [
        "Citation assembly benchmark active.",
        "Ingest and search benchmarks pending implementation (ADR-005).",
    ]
    if search_only:
        note_parts.append("--search-only ignored until search service exists.")

    return BenchmarkResult(
        timestamp=datetime.now(UTC).isoformat(),
        environment=env,
        status="partial",
        citation_assembly_ms=citation_stats,
        note=" ".join(note_parts),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base benchmark")
    parser.add_argument("--iterations", type=int, default=100)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--search-only", action="store_true")
    args = parser.parse_args()

    result = run_benchmark(iterations=args.iterations, search_only=args.search_only)

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"Knowledge Base Benchmark ({result.status})")
        print(f"  Platform: {result.environment['platform']}")
        if result.citation_assembly_ms:
            s = result.citation_assembly_ms
            print(f"  Citation assembly (ms): mean={s.mean} p50={s.p50} p95={s.p95}")
        print(f"  Note: {result.note}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
