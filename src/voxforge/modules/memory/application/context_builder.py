from dataclasses import dataclass

from voxforge.core.domain.entities import MessageRole
from voxforge.core.domain.memory import MemoryContext, MemoryEntry


@dataclass
class ChatMessageLike:
    role: MessageRole
    content: str


class ContextBuilder:
    """Compress conversation history with summary + semantic retrieval."""

    def build(
        self,
        *,
        system_prompt: str,
        recent_messages: list[ChatMessageLike],
        memory_context: MemoryContext,
        max_recent_messages: int,
    ) -> list[ChatMessageLike]:
        messages: list[ChatMessageLike] = [
            ChatMessageLike(role=MessageRole.SYSTEM, content=system_prompt)
        ]

        if memory_context.summary:
            messages.append(
                ChatMessageLike(
                    role=MessageRole.SYSTEM,
                    content=(f"Conversation summary so far:\n{memory_context.summary}"),
                )
            )

        if memory_context.relevant_entries:
            memory_block = self._format_retrieved(memory_context.relevant_entries)
            messages.append(
                ChatMessageLike(
                    role=MessageRole.SYSTEM,
                    content=f"Relevant context from memory:\n{memory_block}",
                )
            )

        tail = [m for m in recent_messages if m.role != MessageRole.SYSTEM]
        if len(tail) > max_recent_messages:
            tail = tail[-max_recent_messages:]

        messages.extend(tail)
        return messages

    @staticmethod
    def _format_retrieved(entries: list[MemoryEntry]) -> str:
        lines = []
        for entry in entries:
            prefix = entry.role.upper()
            score = f" (relevance {entry.similarity:.2f})" if entry.similarity else ""
            lines.append(f"- [{prefix}]{score}: {entry.content}")
        return "\n".join(lines)
