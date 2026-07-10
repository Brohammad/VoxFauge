# Resume Bullet Points

Use these for senior/staff software engineer applications.

## Platform engineering

- Architected and shipped **VoxForge**, an open-source voice AI infrastructure platform (Python/FastAPI, PostgreSQL/pgvector, Redis, Docker) with **354+ automated tests** and **81% code coverage**.

- Designed a **unified voice pipeline** serving WebSocket, programmatic onboarding, and LiveKit WebRTC through a single `VoicePipelineService`, eliminating transport-specific business logic duplication.

## Reliability & operations

- Built **production deployment automation** (Docker Compose, NGINX, Let's Encrypt) with health/readiness probes, graceful shutdown, backup/restore, and a live deployment at **voxforge.brohammad.tech**.

- Implemented **defense-in-depth security**: CSP/HSTS headers, rate limiting, JWT/RBAC/SAML SSO, pip-audit, and gitleaks secret scanning in CI.

## AI / voice systems

- Integrated **multi-provider STT/LLM/TTS** with mock adapters for zero-friction demos and swappable production providers via environment configuration.

- Delivered **knowledge RAG pipeline** (document ingestion, chunking, pgvector search) with citation grounding in the agent orchestrator.

## Observability & quality

- Shipped **per-turn evaluation engine** with latency breakdown, quality scoring, session replay, and operator dashboard analytics.

- Added **Playwright browser test suite** (8 critical user journeys) running in CI alongside unit, integration, feature, and failure-mode tests.

## Leadership / OSS

- Published **ADRs, deployment runbooks, pilot onboarding guides**, and competitive benchmark against Vapi, Retell, and LiveKit Agents.

- Established open-source governance: CONTRIBUTING, SECURITY, CODE_OF_CONDUCT, issue templates, and semantic versioning with CHANGELOG.
