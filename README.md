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

## Architecture

VoxForge is a modular monolith built with Clean Architecture principles:

- **Authentication** — JWT, RBAC, organizations, API keys
- **Voice Gateway** — WebSocket transport for real-time audio streaming
- **Session Manager** — Voice session lifecycle and reconnect support
- **STT Module** — Streaming speech recognition (Deepgram)
- **Conversation Engine** — Streaming LLM responses (OpenAI)
- **TTS Module** — Streaming text-to-speech (Cartesia)

See [docs/architecture/voice-pipeline.md](docs/architecture/voice-pipeline.md) for details.

## Development

```bash
# Run tests
pytest

# Lint
ruff check src tests

# Test voice WebSocket
python scripts/test_voice_ws.py
```
