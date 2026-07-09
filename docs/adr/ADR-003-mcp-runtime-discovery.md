# ADR-003: MCP Runtime Discovery

## Status

Accepted (2026-07-10)

## Context

MCP tools were registered from static `tools` arrays inside `MCP_SERVERS_CONFIG`. That
required operators to duplicate tool metadata already exposed by MCP servers via
`list_tools()`, created drift risk, and prevented health visibility per server.

Phase 3 requires infrastructure-grade discovery without framework coupling or startup
regression.

## Decision

Introduce `MCPRuntimeRegistry` as the infrastructure component that:

1. Parses server configuration (`mcp_config.py`)
2. Discovers tools at startup via `StdioMCPDiscoveryClient.list_tools()` when
   `MCP_STARTUP_DISCOVER=true`
3. Indexes tools in `dict[str, ToolDefinition]` for **O(1)** lookup post-init
4. Falls back to static config metadata when discovery fails (`degraded` status)
5. Never blocks application startup on provider failure (isolated per-server timeouts)
6. Exposes health via `GET /api/v1/tools/mcp/health` and server metadata via
   `GET /api/v1/tools/mcp/servers`

`ToolRegistry` depends on the registry port, not vendor SDKs. `MCPToolAdapter` remains as a
thin backward-compatible facade.

### Permission model (future-ready)

Server config may declare:

```json
"permissions": ["tools:execute"],
"capabilities": ["filesystem", "search"]
```

These propagate to `ToolDefinition.required_scopes` and `MCPServerRecord` for policy engines.

### Hot registration (future-ready)

`MCPRuntimeRegistry.register_server()` / `unregister_server()` exist but are not exposed via
HTTP in Phase 3.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Keep static config only | Drift, no health, poor interview/production story |
| Discover on every tool call | Violates latency target; adds provider load |
| LangGraph-native tool loading | Framework coupling; breaks hexagonal boundaries |
| Block startup on MCP failure | Violates reliability requirement |

## Consequences

**Positive**

- Dynamic tool metadata from real MCP servers
- O(1) tool routing after startup
- Per-server health and capability visibility
- Static config still works (backward compatible)

**Negative**

- Startup discovery adds latency proportional to configured servers (bounded by timeout)
- Tool name collisions across servers: last registration wins (documented)
- Stdio transport only for runtime discovery in Phase 3

## Performance

- No MCP config: discovery ~0 ms
- Mock/stub servers in tests: <1 ms
- Per-server timeout default: 5000 ms (configurable)
- Tool execution path unchanged (same stdio invoke client)
