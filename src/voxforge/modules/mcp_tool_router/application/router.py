import asyncio
import time
from typing import Any
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.tools import ToolCallStatus, ToolDefinition, ToolResult
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    tool_calls_total,
    tool_latency_seconds,
)
from voxforge.modules.mcp_tool_router.application.registry import ToolRegistry

logger = get_logger(__name__)


class ToolRouter:
    """Routes tool invocations to registered handlers with audit logging."""

    def __init__(
        self,
        registry: ToolRegistry,
        settings: Settings,
        call_repository: Any | None = None,
    ) -> None:
        self._registry = registry
        self._settings = settings
        self._repo = call_repository

    def list_tools(self) -> list[ToolDefinition]:
        if not self._settings.tools_enabled:
            return []
        return self._registry.list_definitions()

    def get_langchain_tools(self) -> list[Any]:
        if not self._settings.tools_enabled:
            return []
        return self._registry.get_langchain_tools()

    async def execute(
        self,
        tool_name: str,
        arguments: dict[str, Any],
        *,
        org_id: UUID | None = None,
        session_id: UUID | None = None,
    ) -> ToolResult:
        start = time.monotonic()
        status = ToolCallStatus.SUCCESS
        output = ""
        error: str | None = None

        try:
            if self._registry.is_mcp_tool(tool_name):
                result = await asyncio.wait_for(
                    self._registry.invoke_mcp(tool_name, arguments),
                    timeout=self._settings.tool_timeout_seconds,
                )
            else:
                handler = self._registry.get_handler(tool_name)
                if handler is None:
                    raise ValueError(f"Unknown tool: {tool_name}")
                output = await asyncio.wait_for(
                    handler.invoke(arguments),
                    timeout=self._settings.tool_timeout_seconds,
                )
                result = ToolResult(tool_name=tool_name, output=output)
            output = result.output
            status = result.status
            error = result.error
        except TimeoutError:
            status = ToolCallStatus.TIMEOUT
            error = f"Tool '{tool_name}' timed out"
        except Exception as exc:
            status = ToolCallStatus.ERROR
            error = str(exc)
            logger.error("tool_execution_error", tool=tool_name, error=error)

        latency_ms = (time.monotonic() - start) * 1000
        tool_calls_total.labels(tool_name=tool_name, status=status.value).inc()
        tool_latency_seconds.labels(tool_name=tool_name).observe(latency_ms / 1000)

        final = ToolResult(
            tool_name=tool_name,
            output=output,
            status=status,
            latency_ms=latency_ms,
            error=error,
        )

        if self._repo is not None:
            await self._repo.record_call(
                org_id=org_id,
                session_id=session_id,
                tool_name=tool_name,
                arguments=arguments,
                result=output,
                status=status,
                latency_ms=latency_ms,
                error=error,
            )

        return final
