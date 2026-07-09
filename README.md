# VoxForge

Production-grade Voice AI Infrastructure Platform for enterprise applications.

## Quick Start

```bash
# Copy environment variables
cp .env.example .env

# Start infrastructure
docker compose up -d postgres redis

# Install dependencies
pip install -e ".[dev]"

# Run migrations
alembic upgrade head

# Start the API server
uvicorn voxforge.main:app --reload --app-dir src
```

API docs: http://localhost:8000/api/v1/docs

Landing: http://localhost:8000/

Demo: http://localhost:8000/demo

Dashboard: http://localhost:8000/dashboard

## Production deployment

See [docs/deployment/guide.md](docs/deployment/guide.md) for VPS deployment with Docker Compose, NGINX, HTTPS, and the public demo.

```bash
cp .env.production.example .env.production
# Edit secrets, then on your VPS:
./deploy.sh init
```

## Architecture

VoxForge is a modular monolith built with Clean Architecture principles:

- **Authentication** — JWT, RBAC, organizations, API keys
- **Agent Orchestrator** — LangGraph multi-agent pipeline (planner, safety, executor, critic, coordinator)
- **Memory** — Semantic retrieval, summarization, and context compression (pgvector)
- **MCP Tool Router** — Builtin tools + MCP server integration for agent executor
- **Evaluation Engine** — Per-turn latency, quality, tool, and cost scoring
- **Dashboard** — Web UI + analytics API for sessions, latency, evaluations, activity, outcomes
- **Voice Gateway** — WebSocket transport for real-time audio streaming
- **Session Manager** — Voice session lifecycle and reconnect support
- **STT Module** — Streaming speech recognition (Deepgram)
- **Conversation Engine** — Streaming LLM responses (OpenAI)
- **TTS Module** — Streaming text-to-speech (Cartesia)

See [docs/architecture/voice-pipeline.md](docs/architecture/voice-pipeline.md) for details.

Pilot value checklist: [docs/product/prove-value-in-1-day.md](docs/product/prove-value-in-1-day.md).

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests

# Test voice WebSocket
python scripts/test_voice_ws.py
```
