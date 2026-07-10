# Knowledge Base Benchmarks

Baseline measurements for enterprise knowledge base ingestion, semantic search,
and citation assembly. Use this document to track regressions as the KB module
is implemented per [ADR-005](../adr/ADR-005-enterprise-knowledge-base.md).

## Reproduce

```bash
make benchmark-knowledge-base
```

JSON output (for CI artifacts and diffs):

```bash
make benchmark-knowledge-base-json
```

Full benchmark (after Phase 3 — ingest + search):

```bash
python scripts/benchmark_knowledge_base.py --iterations 20 --json
```

## Methodology

| Parameter | Value |
|-----------|-------|
| Corpus | Synthetic 1 MB PDF, 10k text chunks (post-implementation) |
| Embedder | Mock / fixed-dimension local embedder (no API keys) |
| Vector store | PostgreSQL pgvector with HNSW index |
| Database | Postgres in CI; SQLite for unit-level parser tests |
| Warmup | 3 iterations (discarded) |
| Measured iterations | 20 |
| External provider latency | **Excluded** — mocks return immediately |

### Metrics collected

| Metric | Definition |
|--------|------------|
| **Ingest wall clock** | Upload to `status=ready` including parse, chunk, embed, index |
| **Parse stage** | Raw bytes → `ParsedDocument` |
| **Chunk stage** | `ParsedDocument` → `list[RawChunk]` |
| **Embed stage** | `embed_batch()` for all chunks |
| **Index stage** | pgvector upsert + HNSW visibility |
| **Search p50/p95** | Query embed + pgvector cosine search + citation assembly |
| **Citation assembly** | `build_citation()` + `format_context_snippets()` per result |
| **Incremental update** | Re-upload with 10% changed chunks — embed count vs full re-index |

## Engineering targets

| Metric | Target | Phase |
|--------|--------|-------|
| Citation assembly p95 | < 5 ms | 1 (active) |
| Search p95 (10k chunks) | < 100 ms excl. embed API | 3 |
| Ingest 1 MB PDF | < 30 s excl. embed API | 2 |
| Incremental (10% changed) | < 20% of full ingest time | 2 |
| Queue depth recovery | < 60 s after worker restart | 2 |

## Baseline (2026-07-10) — partial

**Status:** Full benchmark active (upload, index, search, retrieval, citation).

**Environment**

| Field | Value |
|-------|-------|
| Machine | Apple Silicon Mac (arm64) |
| OS | macOS 26.5 |
| Python | 3.14 |
| Embedder | Mock (hash-seeded unit vectors) |
| Database | SQLite in-memory (CI-compatible) |

### Throughput and latency (5 measured iterations, 1 warmup)

| Metric | Mean | p50 | p95 |
|--------|------|-----|-----|
| Upload throughput (docs/s) | 177 | 204 | — |
| Search latency (ms) | 4.3 | 4.3 | 4.5 |
| Retrieval latency (ms) | 3.9 | 3.9 | 4.1 |
| Citation assembly (ms) | 0.009 | 0.004 | 0.03 |

Run `make benchmark-knowledge-base-json` to refresh after environment changes.

**Interpretation:** With mock embedder, search and retrieval are dominated by in-process Python + SQLite. Production latency will include Postgres pgvector and embedding API time.

## Current limitations

1. **Mock embedder** — does not measure OpenAI embedding API latency.
2. **Synthetic corpus** — real PDF complexity (tables, images) not represented.
3. **Single worker** — no concurrent ingest load testing.
4. **No OCR** — scanned PDFs excluded from v1 benchmarks.

## Comparison workflow

After each phase:

```bash
python scripts/benchmark_knowledge_base.py --iterations 20 --json > /tmp/kb-bench-after.json
```

Compare `citation_assembly_ms.p95`, and (post-Phase 3) `search_latency_ms.p95` and
`ingest_wall_clock_ms.p95` against baseline.

## CI integration (proposed)

Add to `.github/workflows/ci.yml` after Phase 3:

```yaml
- name: Knowledge base benchmark
  run: make benchmark-knowledge-base-json
  continue-on-error: true
```

Gate thresholds (future `scripts/knowledge_gate.py`):

- Citation assembly p95 < 5 ms
- Search p95 < 100 ms (mock embedder, 10k chunks)
- Zero org-isolation test failures

## Related docs

- [ADR-005: Enterprise Knowledge Base](../adr/ADR-005-enterprise-knowledge-base.md)
- [Knowledge Base Architecture](../architecture/knowledge-base.md)
- [Onboarding Pipeline Benchmark](./onboarding.md)
