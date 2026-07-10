# Frequently Asked Questions

## Do I need API keys to try VoxForge locally?

No. Copy `.env.example` — mock STT/LLM/TTS/embedding providers work without paid keys. `DEMO_ENABLED=true` enables the public demo.

## How do I deploy to production?

See [docs/deployment/guide.md](deployment/guide.md). Summary: Ubuntu VPS → `./scripts/setup-production-env.sh your-domain.example` → `./deploy.sh init`.

## Why does `/demo` return 404?

Set `DEMO_ENABLED=true` in `.env` and restart the server.

## Can I use real voice providers?

Yes. Set `STT_PROVIDER=deepgram`, `LLM_PROVIDER=openai`, `TTS_PROVIDER=cartesia` and provide API keys. Production validation requires real providers when `DEMO_ENABLED=false`.

## How do knowledge base uploads get processed?

With `KNOWLEDGE_WORKER_ENABLED=false` (default local), ingestion runs inline. In production, enable the `knowledge` compose profile or set `KNOWLEDGE_WORKER_ENABLED=true` — `deploy.sh` starts the worker automatically.

## Is LiveKit required?

No. WebSocket voice works without LiveKit. LiveKit enables WebRTC browser audio — set `LIVEKIT_URL` and start the `livekit` worker profile.

## How do I run browser tests?

```bash
make test-browser
```

Requires Postgres + Redis running locally.

## What is the test coverage gate?

70% minimum in CI (`--cov-fail-under=70`). Target for business logic is 90% per testing strategy.

## Known limitations

See [docs/release/known-limitations.md](release/known-limitations.md).
