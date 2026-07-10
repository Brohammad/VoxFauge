#!/usr/bin/env python3
"""Reproducible benchmark for enterprise knowledge base ingestion and search.

Measures upload throughput, indexing throughput, search latency, retrieval latency,
and citation assembly using mock providers (no API keys required).

Usage:
    python scripts/benchmark_knowledge_base.py
    python scripts/benchmark_knowledge_base.py --iterations 20 --json
    python scripts/benchmark_knowledge_base.py --search-only --json
"""

from __future__ import annotations

import argparse
import asyncio
import json
import platform
import sys
import time
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_ROOT / "src"))

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from voxforge.config import Settings
from voxforge.core.domain.knowledge import (
    ChunkMetadata,
    KnowledgeChunk,
    KnowledgeDocument,
    KnowledgeDocumentVersion,
    KnowledgeSearchRequest,
    SourceType,
)
from voxforge.infrastructure.db.base import Base
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.knowledge.blob import create_blob_store
from voxforge.infrastructure.providers.embeddings.mock import MockEmbeddingProvider
from voxforge.infrastructure.providers.support.internal import InternalKnowledgeBaseProvider
from voxforge.infrastructure.tools.tool_context import tool_org_id
from voxforge.modules.knowledge.application.citation import build_citation, format_context_snippets
from voxforge.modules.knowledge.application.ingestion_service import KnowledgeIngestionService
from voxforge.modules.knowledge.application.search_service import KnowledgeSearchService


@dataclass
class LatencyStats:
    mean: float
    p50: float
    p95: float
    min: float
    max: float


@dataclass
class ThroughputStats:
    mean_per_sec: float
    p50_per_sec: float
    p95_per_sec: float


@dataclass
class BenchmarkResult:
    timestamp: str
    environment: dict
    status: str
    upload_throughput_docs_per_sec: ThroughputStats | None = None
    indexing_throughput_chunks_per_sec: ThroughputStats | None = None
    search_latency_ms: LatencyStats | None = None
    retrieval_latency_ms: LatencyStats | None = None
    citation_assembly_ms: LatencyStats | None = None
    corpus_chunks: int = 0
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


def _throughput_stats(samples: list[float]) -> ThroughputStats:
    latency = _percentile_stats(samples)
    def inv(x: float) -> float:
        return round(1000.0 / x, 3) if x > 0 else 0.0

    return ThroughputStats(
        mean_per_sec=inv(latency.mean),
        p50_per_sec=inv(latency.p50),
        p95_per_sec=inv(latency.p95),
    )


def _benchmark_citation_assembly(iterations: int) -> LatencyStats:
    now = datetime.now(UTC)
    doc_id = uuid4()
    version_id = uuid4()
    org_id = uuid4()

    document = KnowledgeDocument(
        id=doc_id,
        org_id=org_id,
        collection_id=uuid4(),
        title="Benchmark Document",
        source_type=SourceType.MARKDOWN,
        content_hash="hash",
        created_at=now,
        updated_at=now,
    )
    version = KnowledgeDocumentVersion(
        id=version_id,
        document_id=doc_id,
        version_number=1,
        content_hash="hash",
        blob_path="bench/doc.md",
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


async def _setup_benchmark_db():
    from uuid import uuid4

    from voxforge.infrastructure.db.models import OrganizationModel

    org_id = uuid4()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as session:
        session.add(
            OrganizationModel(
                id=org_id,
                name="Benchmark Org",
                slug=f"bench-{uuid4().hex[:8]}",
            )
        )
        await session.commit()
    return engine, factory, org_id


async def _seed_corpus(
    *,
    org_id,
    collection_id,
    repo: KnowledgeRepository,
    embedder: MockEmbeddingProvider,
    chunk_count: int = 50,
) -> None:
    now = datetime.now(UTC)
    document = await repo.create_document(
        org_id=org_id,
        collection_id=collection_id,
        title="Benchmark Corpus",
        source_type=SourceType.TXT,
        content_hash="bench-corpus",
    )
    version = await repo.create_version(
        document_id=document.id,
        version_number=1,
        content_hash="bench-corpus",
        blob_path="bench/corpus.txt",
    )
    from voxforge.core.domain.knowledge import RawChunk

    chunks = [
        RawChunk(
            chunk_index=i,
            content=f"Benchmark knowledge chunk {i} about refunds billing and support policies.",
            metadata=ChunkMetadata(),
        )
        for i in range(chunk_count)
    ]
    embeddings = await embedder.embed_batch([c.content for c in chunks])
    await repo.upsert_chunks(
        org_id=org_id,
        document_version_id=version.id,
        chunks=list(zip(chunks, embeddings, strict=True)),
    )
    await repo.set_active_version(document.id, org_id=org_id, version_id=version.id)


async def run_benchmark(*, iterations: int, warmup: int, search_only: bool) -> BenchmarkResult:
    env = {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
    }
    citation_stats = _benchmark_citation_assembly(iterations)

    if search_only:
        return BenchmarkResult(
            timestamp=datetime.now(UTC).isoformat(),
            environment=env,
            status="partial",
            citation_assembly_ms=citation_stats,
            note="Search-only mode: ingest benchmarks skipped.",
        )

    settings = Settings(
        knowledge_enabled=True,
        knowledge_worker_enabled=False,
        embedding_provider="mock",
        knowledge_blob_path="/tmp/voxforge-kb-bench",
        knowledge_search_min_similarity=0.0,
    )
    engine, factory, org_id = await _setup_benchmark_db()
    upload_samples: list[float] = []
    index_samples: list[float] = []
    search_samples: list[float] = []
    retrieval_samples: list[float] = []
    corpus_chunks = 0

    try:
        async with factory() as session:
            repo = KnowledgeRepository(session)
            embedder = MockEmbeddingProvider()
            blob = create_blob_store(settings.knowledge_blob_store, path=settings.knowledge_blob_path)
            ingest = KnowledgeIngestionService(repo, blob, embedder, settings)
            search = KnowledgeSearchService(repo, embedder, settings)

            collection = await repo.create_collection(org_id=org_id, name="bench")
            await session.commit()

            content = (
                b"# Support Policy\n\nCustomers may request refunds within 30 days. "
                b"Billing disputes require invoice ID. Enterprise accounts contact billing."
            )

            for i in range(warmup):
                await ingest.upload_document(
                    org_id=org_id,
                    collection_id=collection.id,
                    filename=f"warmup-{i}.md",
                    content=content,
                    title=f"Warmup {i}",
                )
                await session.commit()

            for i in range(iterations):
                start = time.perf_counter()
                _doc_id, _job_id = await ingest.upload_document(
                    org_id=org_id,
                    collection_id=collection.id,
                    filename=f"bench-{i}.md",
                    content=content,
                    title=f"Benchmark {i}",
                )
                upload_samples.append((time.perf_counter() - start) * 1000)
                await session.commit()

            await _seed_corpus(
                org_id=org_id,
                collection_id=collection.id,
                repo=repo,
                embedder=embedder,
                chunk_count=50,
            )
            corpus_chunks = 50
            await session.commit()

            index_start = time.perf_counter()
            _doc_id, _job_id = await ingest.upload_document(
                org_id=org_id,
                collection_id=collection.id,
                filename="index-bench.md",
                content=content * 20,
                title="Index Benchmark",
            )
            index_samples.append((time.perf_counter() - index_start) * 1000)
            await session.commit()

            query = "refund policy billing invoice enterprise"
            for _ in range(warmup):
                await search.search(
                    org_id=org_id,
                    request=KnowledgeSearchRequest(query=query, limit=5, min_similarity=0.0),
                )

            for _ in range(iterations):
                start = time.perf_counter()
                await search.search(
                    org_id=org_id,
                    request=KnowledgeSearchRequest(query=query, limit=5, min_similarity=0.0),
                )
                search_samples.append((time.perf_counter() - start) * 1000)

            provider = InternalKnowledgeBaseProvider(factory, settings)
            token = tool_org_id.set(org_id)
            try:
                for _ in range(warmup):
                    await provider.search(query, limit=3)
                for _ in range(iterations):
                    start = time.perf_counter()
                    await provider.search(query, limit=3)
                    retrieval_samples.append((time.perf_counter() - start) * 1000)
            finally:
                tool_org_id.reset(token)

    finally:
        await engine.dispose()

    return BenchmarkResult(
        timestamp=datetime.now(UTC).isoformat(),
        environment=env,
        status="complete",
        upload_throughput_docs_per_sec=_throughput_stats(upload_samples),
        indexing_throughput_chunks_per_sec=_throughput_stats(index_samples),
        search_latency_ms=_percentile_stats(search_samples),
        retrieval_latency_ms=_percentile_stats(retrieval_samples),
        citation_assembly_ms=citation_stats,
        corpus_chunks=corpus_chunks,
        note="Mock embedder; external API latency excluded.",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Knowledge base benchmark")
    parser.add_argument("--iterations", type=int, default=20)
    parser.add_argument("--warmup", type=int, default=3)
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--search-only", action="store_true")
    args = parser.parse_args()

    result = asyncio.run(
        run_benchmark(
            iterations=args.iterations,
            warmup=args.warmup,
            search_only=args.search_only,
        )
    )

    if args.json:
        print(json.dumps(asdict(result), indent=2))
    else:
        print(f"Knowledge Base Benchmark ({result.status})")
        print(f"  Platform: {result.environment['platform']}")
        if result.upload_throughput_docs_per_sec:
            u = result.upload_throughput_docs_per_sec
            print(f"  Upload throughput (docs/s): mean={u.mean_per_sec} p50={u.p50_per_sec}")
        if result.search_latency_ms:
            s = result.search_latency_ms
            print(f"  Search latency (ms): mean={s.mean} p50={s.p50} p95={s.p95}")
        if result.retrieval_latency_ms:
            r = result.retrieval_latency_ms
            print(f"  Retrieval latency (ms): mean={r.mean} p50={r.p50} p95={r.p95}")
        if result.citation_assembly_ms:
            c = result.citation_assembly_ms
            print(f"  Citation assembly (ms): mean={c.mean} p50={c.p50} p95={c.p95}")
        print(f"  Note: {result.note}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
