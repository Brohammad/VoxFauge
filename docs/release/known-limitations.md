# Known Limitations (RC-1)

## Voice

- **Microphone / real STT streaming** — WebSocket lifecycle is tested; browser microphone capture is not automated in CI.
- **Barge-in** — Not exercised in automated browser tests.
- **LiveKit worker** — Requires external LiveKit Cloud or self-hosted server; optional compose profile.

## Integrations

- **Zendesk / Freshdesk** — Provider stubs raise `ProviderError`; do not set in production.
- **MCP servers** — Require `pip install -e ".[mcp]"` in production image when `MCP_SERVERS_CONFIG` is set.

## Operations

- **Single uvicorn worker** — Production compose uses one worker by design; document before scaling.
- **Grafana** — Bound to localhost; requires SSH tunnel for remote access.

## Security

- **Dashboard JWT in localStorage** — Mitigate XSS in operator environments; httpOnly cookies planned for v1.1.

## Documentation

- Screenshots and demo GIF are placeholders — capture after RC-1 UI freeze.
