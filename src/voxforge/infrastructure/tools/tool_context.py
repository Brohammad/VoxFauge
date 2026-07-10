"""Request-scoped context for in-process tool execution."""

from __future__ import annotations

from contextvars import ContextVar
from uuid import UUID

tool_org_id: ContextVar[UUID | None] = ContextVar("tool_org_id", default=None)
tool_session_id: ContextVar[UUID | None] = ContextVar("tool_session_id", default=None)
