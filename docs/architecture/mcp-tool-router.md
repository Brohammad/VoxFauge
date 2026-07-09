# MCP Tool Router Architecture

## Overview

The MCP Tool Router provides a **provider-agnostic tool execution layer** for the agent
orchestrator, with builtin tools and optional MCP server integration.

See [mcp-runtime-discovery.md](mcp-runtime-discovery.md) for Phase 3 runtime discovery design.

```mermaid
flowchart LR
    Executor[Executor Agent] --> Router[ToolRouter]
    Router --> Registry[ToolRegistry]
    Registry --> Builtin[Builtin Tools]
    Registry --> MCPReg[MCPRuntimeRegistry]
    MCPReg --> Discovery[StdioMCPDiscoveryClient]
    MCPReg --> Invoke[StdioMCPInvocationClient]
    Router --> DB[(tool_calls)]
```

## Builtin Tools

| Tool | Description |
|------|-------------|
| `get_current_time` | Current UTC timestamp |
| `calculate` | Safe math expression evaluator |
| `echo` | Echo message (testing) |

## MCP Integration

Configure external MCP servers via JSON in `MCP_SERVERS_CONFIG`:

```json
[
  {
    "id": "filesystem",
    "name": "Filesystem",
    "transport": "stdio",
    "command": "npx",
    "args": ["-y", "@modelcontextprotocol/server-filesystem", "/tmp"],
    "permissions": ["tools:execute"],
    "capabilities": ["filesystem"]
  }
]
```

At startup, VoxForge calls `list_tools()` on each server and registers discovered metadata.
Static `tools` arrays remain supported as a degraded fallback.

Requires `pip install mcp` for stdio MCP client support.

## Agent Integration

When `ORCHESTRATOR_MODE=multi_agent` and `TOOLS_ENABLED=true`, the **executor** agent:

1. Binds LangChain tools to the LLM
2. Executes tool calls via `ToolRouter`
3. Emits `agent_step` events with `agent: "tool"`
4. Persists calls to `tool_calls` table

## API

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/v1/tools` | List available tools |
| GET | `/api/v1/tools/mcp/health` | MCP registry health |
| GET | `/api/v1/tools/mcp/servers` | MCP server capabilities |
| GET | `/api/v1/sessions/{id}/tool-calls` | Tool call history for session |

## Configuration

```env
TOOLS_ENABLED=true
TOOL_TIMEOUT_SECONDS=30
MAX_TOOL_ITERATIONS=5
MCP_SERVERS_CONFIG=
MCP_DISCOVERY_ENABLED=true
MCP_DISCOVERY_TIMEOUT_MS=5000
MCP_STARTUP_DISCOVER=true
```

## Metrics

- `voxforge_tool_calls_total{tool_name, status}`
- `voxforge_tool_latency_seconds{tool_name}`
- `voxforge_mcp_discovery_duration_seconds`
- `voxforge_mcp_servers_total{status}`
