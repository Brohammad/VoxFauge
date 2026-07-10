"""Conversation summarization for human handoff context."""

from __future__ import annotations

from uuid import UUID

from voxforge.core.domain.entities import MessageRole
from voxforge.modules.session_manager.application.service import SessionManager


class ExtractiveConversationSummarizer:
    """Build a concise summary from recent session messages (no LLM required)."""

    def __init__(self, session_manager: SessionManager) -> None:
        self._sessions = session_manager

    async def summarize(
        self,
        *,
        session_id: UUID,
        org_id: UUID,
        max_messages: int = 50,
    ) -> str:
        _ = org_id
        messages = await self._sessions.get_messages(session_id, offset=0, limit=max_messages)
        if not messages:
            return "No prior conversation messages."

        lines: list[str] = []
        for message in messages:
            role = message.role.value if isinstance(message.role, MessageRole) else str(message.role)
            content = message.content.strip().replace("\n", " ")
            if len(content) > 240:
                content = content[:237] + "..."
            lines.append(f"{role}: {content}")

        summary = "\n".join(lines)
        if len(summary) > 4000:
            summary = summary[:3997] + "..."
        return summary
