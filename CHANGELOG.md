# Changelog

All notable changes to VoxForge are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### RC-1 (2026-07-10)

#### Added
- Playwright browser test suite (`tests/browser/`) with CI job
- `Dockerfile.dev` for local development; `docker-compose.smoke.yml` for prod smoke tests
- `deploy.sh smoke` and `scripts/validate-prod-smoke.sh` for local production validation
- Content-Security-Policy headers (UI vs API policies)
- OpenTelemetry FastAPI auto-instrumentation
- Deployment verification checklist, FAQ, roadmap, known limitations

#### Changed
- Production compose: app healthchecks; workers wait for healthy app
- `.env.production.example` uses placeholder domain; `setup-production-env.sh` accepts domain argument

#### Removed
- Dead code: `mcp_adapter.py`, unused `Evaluator`/`ToolHandler` interfaces, empty `stt`/`tts` modules

### Added (pre-RC)
- Security headers middleware for direct app access (X-Content-Type-Options, X-Frame-Options, HSTS in production).
- Dashboard email/password login alongside JWT paste.
- Friendly API error parsing in the operator dashboard.
- Demo page guidance when `DEMO_ENABLED=false`.
- `CONTRIBUTING.md`, `SECURITY.md`, GitHub issue/PR templates.
- Explicit `cryptography` dependency for SAML support.

### Changed
- `.env.example` enables `DEMO_ENABLED=true` and mock voice providers for local development.
- Production validation now requires `PUBLIC_BASE_URL`, `CORS_ORIGINS`, dedicated `HANDOFF_REPLAY_SIGNING_SECRET`, and blocks mock providers when `DEMO_ENABLED=false`.
- Knowledge search uses a permissive default similarity threshold when `EMBEDDING_PROVIDER=mock`.
- Unsupported knowledge upload file types are rejected with HTTP 415.

### Fixed
- Dev Docker image failed to start due to missing `cryptography` import.
- Landing and demo pages returned 404 in `docker compose` (missing `public/` assets).
- Dashboard knowledge search returned no results with mock embeddings.

## [0.1.0] - 2026-07-10

### Added
- Modular monolith voice AI platform: WebSocket gateway, programmatic onboarding pipeline, LiveKit integration.
- Authentication (JWT, API keys, organizations, SAML SSO).
- Knowledge base with pgvector semantic search and document ingestion.
- Human handoff queue with replay links and mock ticketing.
- Evaluation engine, session replay, operator dashboard, and Prometheus metrics.
- Production deployment path: Docker Compose, NGINX, TLS, `deploy.sh`, CI pipeline.

[Unreleased]: https://github.com/Brohammad/VoxForge/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Brohammad/VoxForge/releases/tag/v0.1.0
