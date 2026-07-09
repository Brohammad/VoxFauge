from __future__ import annotations

import asyncio
import time
from typing import Any

from voxforge.config import Settings
from voxforge.core.domain.mcp import MCPRegistryHealth, MCPServerRecord, MCPServerStatus
from voxforge.core.domain.tools import ToolCallStatus, ToolDefinition, ToolResult
from voxforge.core.interfaces.mcp import MCPDiscoveryClient, MCPInvocationClient
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    mcp_discovery_duration_seconds,
    mcp_servers_total,
)
from voxforge.infrastructure.observability.telemetry import get_tracer
from voxforge.infrastructure.tools.mcp_config import parse_mcp_servers_config, server_id_for
from voxforge.infrastructure.tools.mcp_stdio_client import (
    StdioMCPDiscoveryClient,
    StdioMCPInvocationClient,
)

logger = get_logger(__name__)
_tracer = get_tracer(__name__)


class MCPRuntimeRegistry:
    """Runtime registry for dynamically discovered MCP tools with O(1) lookup."""

    def __init__(
        self,
        settings: Settings,
        *,
        discovery_client: MCPDiscoveryClient | None = None,
        invocation_client: MCPInvocationClient | None = None,
    ) -> None:
        self._settings = settings
        self._discovery = discovery_client or StdioMCPDiscoveryClient()
        self._invocation = invocation_client or StdioMCPInvocationClient()
        self._servers: list[dict[str, Any]] = []
        self._server_records: dict[str, MCPServerRecord] = {}
        self._tool_index: dict[str, ToolDefinition] = {}
        self._tool_server_map: dict[str, str] = {}
        self._discovery_ms: float | None = None

        for index, server in enumerate(parse_mcp_servers_config(settings.mcp_servers_config)):
            enriched = dict(server)
            enriched["_server_id"] = server_id_for(server, index)
            self._servers.append(enriched)

    @property
    def discovery_ms(self) -> float | None:
        return self._discovery_ms

    async def discover_all(self) -> float:
        """Discover tools from all configured servers. Failures are isolated."""
        if not self._settings.mcp_discovery_enabled or not self._servers:
            self._discovery_ms = 0.0
            return 0.0

        start = time.monotonic()
        timeout_s = self._settings.mcp_discovery_timeout_ms / 1000

        with _tracer.start_as_current_span("mcp.registry.discover_all") as span:
            span.set_attribute("voxforge.mcp.server_count", len(self._servers))
            for server in self._servers:
                server_id = server["_server_id"]
                try:
                    tools, record = await asyncio.wait_for(
                        self._discovery.discover(server),
                        timeout=timeout_s,
                    )
                    self._register_server_tools(server_id, server, tools, record)
                except TimeoutError:
                    logger.warning("mcp_discovery_timeout", server_id=server_id)
                    self._register_failed_server(
                        server,
                        error=(
                            f"Discovery timed out after "
                            f"{self._settings.mcp_discovery_timeout_ms}ms"
                        ),
                    )
                except Exception as exc:
                    logger.warning("mcp_discovery_error", server_id=server_id, error=str(exc))
                    self._register_failed_server(server, error=str(exc))

            self._discovery_ms = (time.monotonic() - start) * 1000
            span.set_attribute("voxforge.mcp.discovery_ms", self._discovery_ms)
            span.set_attribute("voxforge.mcp.tool_count", len(self._tool_index))

        mcp_discovery_duration_seconds.observe(self._discovery_ms / 1000)
        logger.info(
            "mcp_discovery_complete",
            server_count=len(self._servers),
            tool_count=len(self._tool_index),
            discovery_ms=self._discovery_ms,
        )
        return self._discovery_ms

    def list_tool_definitions(self) -> list[ToolDefinition]:
        return list(self._tool_index.values())

    def get_tool(self, name: str) -> ToolDefinition | None:
        return self._tool_index.get(name)

    def is_mcp_tool(self, name: str) -> bool:
        return name in self._tool_index

    def list_servers(self) -> list[MCPServerRecord]:
        return list(self._server_records.values())

    def get_health(self) -> MCPRegistryHealth:
        servers = self.list_servers()
        healthy = sum(1 for s in servers if s.status == MCPServerStatus.HEALTHY)
        degraded = sum(1 for s in servers if s.status == MCPServerStatus.DEGRADED)
        offline = sum(1 for s in servers if s.status == MCPServerStatus.OFFLINE)

        if not servers:
            status = "idle"
        elif offline == len(servers):
            status = "offline"
        elif healthy == len(servers):
            status = "healthy"
        else:
            status = "degraded"

        return MCPRegistryHealth(
            status=status,
            server_count=len(servers),
            healthy_count=healthy,
            degraded_count=degraded,
            offline_count=offline,
            tool_count=len(self._tool_index),
            discovery_ms=self._discovery_ms,
            servers=servers,
        )

    async def invoke(self, name: str, arguments: dict[str, Any]) -> ToolResult:
        server_id = self._tool_server_map.get(name)
        if server_id is None:
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error=f"MCP tool '{name}' not found in registry",
            )

        server = next((s for s in self._servers if s["_server_id"] == server_id), None)
        if server is None:
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error=f"MCP server '{server_id}' not found",
            )

        record = self._server_records.get(server_id)
        if record and record.status == MCPServerStatus.OFFLINE:
            return ToolResult(
                tool_name=name,
                output="",
                status=ToolCallStatus.ERROR,
                error=f"MCP server '{server_id}' is offline",
            )

        with _tracer.start_as_current_span("mcp.registry.invoke") as span:
            span.set_attribute("voxforge.mcp.tool_name", name)
            span.set_attribute("voxforge.mcp.server_id", server_id)
            return await self._invocation.invoke(server, name, arguments)

    def register_server(
        self,
        server_config: dict[str, Any],
        tools: list[ToolDefinition],
        record: MCPServerRecord,
    ) -> None:
        """Hot-registration hook (future-ready)."""
        server_id = server_config.get("_server_id") or server_id_for(
            server_config, len(self._servers)
        )
        server_config = {**server_config, "_server_id": server_id}
        if server_config not in self._servers:
            self._servers.append(server_config)
        self._register_server_tools(server_id, server_config, tools, record)

    def unregister_server(self, server_id: str) -> None:
        """Remove a server and its tools from the registry."""
        self._servers = [s for s in self._servers if s.get("_server_id") != server_id]
        self._server_records.pop(server_id, None)
        for tool_name, mapped_server in list(self._tool_server_map.items()):
            if mapped_server == server_id:
                self._tool_index.pop(tool_name, None)
                self._tool_server_map.pop(tool_name, None)
        mcp_servers_total.labels(status="unregistered").inc()

    def _register_server_tools(
        self,
        server_id: str,
        server_config: dict[str, Any],
        tools: list[ToolDefinition],
        record: MCPServerRecord,
    ) -> None:
        self._server_records[server_id] = record
        mcp_servers_total.labels(status=record.status.value).inc()
        for tool in tools:
            self._tool_index[tool.name] = tool
            self._tool_server_map[tool.name] = server_id

    def _register_failed_server(self, server_config: dict[str, Any], *, error: str) -> None:
        server_id = server_config["_server_id"]
        record = MCPServerRecord(
            server_id=server_id,
            name=server_config.get("name", server_id),
            transport=server_config.get("transport", "stdio"),
            status=MCPServerStatus.OFFLINE,
            last_error=error,
            discovery_source="runtime",
        )
        self._server_records[server_id] = record
        mcp_servers_total.labels(status=record.status.value).inc()
