# Knowledge Base — Future Work (Post-MVP)

Explicitly **out of scope** for the current MVP. Track here and via GitHub issues.

| Item | Description | Issue |
|------|-------------|-------|
| Hybrid retrieval | BM25 + vector via Postgres `tsvector` | TBD |
| Metadata filtering | Collection, tag, date, and custom field filters on search | TBD |
| Cross-encoder reranking | Second-stage reranker on top-k vector results | TBD |
| Streaming ingestion | Stream-parse large files; progressive chunk availability | TBD |
| Incremental embedding updates | Partial re-embed on diff without full version swap | TBD |
| S3 blob storage | Production multi-instance blob backend | TBD |
| Multi-region storage | Geo-replicated blobs and read replicas | TBD |

Do not expand MVP scope for these items without a new ADR and review.
