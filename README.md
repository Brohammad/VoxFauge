# VoxForge

[![CI](https://github.com/Brohammad/VoxForge/actions/workflows/ci.yml/badge.svg)](https://github.com/Brohammad/VoxForge/actions/workflows/ci.yml)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Production-grade Voice AI Infrastructure Platform for enterprise applications.

## Quick Start

```bash
cp .env.example .env
docker compose up -d postgres redis
pip install -e ".[dev,livekit]"
alembic upgrade head
uvicorn voxforge.main:app --reload --app-dir src
```

| Surface | URL |
|---------|-----|
| API docs | http://localhost:8000/api/v1/docs |
| Landing | http://localhost:8000/ |
| Demo | http://localhost:8000/demo |
| Dashboard | http://localhost:8000/dashboard |

The demo and dashboard work out of the box with **mock providers** (no API keys). Register an account in the dashboard or use the one-click demo at `/demo`.

## Production deployment

See [docs/deployment/guide.md](docs/deployment/guide.md) for VPS deployment with Docker Compose, NGINX, and HTTPS.

```bash
cp .env.production.example .env.production
# Edit secrets, then on your VPS:
./deploy.sh init
```

Validate before deploy:

```bash
python scripts/validate_production_env.py
```

## Architecture

VoxForge is a modular monolith built with Clean Architecture principles:

| Module | Responsibility |
|--------|----------------|
| **Auth** | JWT, RBAC, organizations, API keys, SAML SSO |
| **Voice Gateway** | WebSocket transport, `VoicePipelineService` orchestration |
| **Agent Orchestrator** | LangGraph multi-agent pipeline (planner, safety, executor, critic) |
| **Memory** | Semantic retrieval, summarization, pgvector |
| **Knowledge** | Document ingestion, chunking, embedding search, citations |
| **Handoff** | Human escalation queue, replay links, ticketing integration |
| **Evaluation** | Per-turn latency, quality, tool, and cost scoring |
| **Dashboard** | Operator UI + analytics API |
| **MCP Tool Router** | Builtin tools + MCP server discovery |
| **LiveKit Gateway** | WebRTC token generation and worker dispatch |

Voice providers (STT, LLM, TTS, embeddings) live in `infrastructure/providers/` and are selected via environment variables.

See [docs/architecture/voice-pipeline.md](docs/architecture/voice-pipeline.md) for the pipeline design.

Pilot value checklist: [docs/product/prove-value-in-1-day.md](docs/product/prove-value-in-1-day.md).

## Development

```bash
make test              # full pytest suite
make test-cov          # with 70% coverage gate
ruff check src tests   # lint

# Voice WebSocket smoke test
python scripts/test_voice_ws.py

# Manual QA harness (running server required)
python scripts/e2e_qa_manual.py
```

See [CONTRIBUTING.md](CONTRIBUTING.md) for contributor guidelines.

## Documentation

- [Deployment guide](docs/deployment/guide.md)
- [Testing strategy](docs/testing/testing-strategy.md)
- [Architecture index](docs/architecture/)
- [ADRs](docs/adr/)
- [Security policy](SECURITY.md)
- [Changelog](CHANGELOG.md)

## License

MIT — see [LICENSE](LICENSE).
