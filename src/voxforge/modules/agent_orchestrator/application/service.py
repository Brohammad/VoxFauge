from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from voxforge.config import Settings
from voxforge.core.domain.entities import Message, MessageRole
from voxforge.core.domain.events import TokenEvent
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.modules.agent_orchestrator.application.graph import build_agent_graph

logger = get_logger(__name__)


@dataclass
class _ChatMessage:
    role: MessageRole
    content: str


class AgentOrchestrator:
    """LangGraph multi-agent orchestrator (planner, safety, executor, critic, coordinator)."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._graph = build_agent_graph(settings)
        self._history: dict[UUID, list[_ChatMessage]] = {}
        self._traces: dict[UUID, list[dict]] = {}

    def init_session(self, session_id: UUID) -> None:
        self._history[session_id] = [
            _ChatMessage(role=MessageRole.SYSTEM, content=self._settings.system_prompt)
        ]
        self._traces[session_id] = []

    def add_user_message(self, session_id: UUID, content: str) -> None:
        if session_id not in self._history:
            self.init_session(session_id)
        self._history[session_id].append(_ChatMessage(role=MessageRole.USER, content=content))

    def add_assistant_message(self, session_id: UUID, content: str) -> None:
        if session_id not in self._history:
            self.init_session(session_id)
        self._history[session_id].append(
            _ChatMessage(role=MessageRole.ASSISTANT, content=content)
        )

    def load_history(self, session_id: UUID, messages: list[Message]) -> None:
        self._history[session_id] = [
            _ChatMessage(role=MessageRole.SYSTEM, content=self._settings.system_prompt)
        ]
        for msg in messages:
            self._history[session_id].append(_ChatMessage(role=msg.role, content=msg.content))

    async def generate_response(
        self,
        session_id: UUID,
        *,
        model: str | None = None,
        on_agent_step: Callable[[str, str, dict], Any] | None = None,
    ) -> AsyncIterator[TokenEvent]:
        history = self._history.get(session_id, [])
        user_input = ""
        for msg in reversed(history):
            if msg.role == MessageRole.USER:
                user_input = msg.content
                break

        messages = [{"role": m.role.value, "content": m.content} for m in history]

        logger.info("agent_orchestrator_run", session_id=str(session_id))
        result = await self._graph.ainvoke({
            "messages": messages,
            "user_input": user_input,
            "plan": "",
            "draft_response": "",
            "safety_passed": True,
            "safety_reason": "",
            "critic_approved": False,
            "critic_feedback": "",
            "final_response": "",
            "iteration": 0,
            "agent_trace": [],
        })

        trace = result.get("agent_trace", [])
        self._traces[session_id] = trace

        if on_agent_step:
            for step in trace:
                await _maybe_await(
                    on_agent_step(step["agent"], step["status"], {"summary": step["summary"]})
                )

        final = result.get("final_response") or result.get("draft_response", "")
        if not final:
            final = "I'm sorry, I couldn't generate a response."

        for word in final.split():
            yield TokenEvent(text=word + " ", is_final=False)
        yield TokenEvent(text="", is_final=True)

    def clear_session(self, session_id: UUID) -> None:
        self._history.pop(session_id, None)
        self._traces.pop(session_id, None)

    def get_last_agent_trace(self, session_id: UUID) -> list[dict]:
        return self._traces.get(session_id, [])


async def _maybe_await(result: Any) -> None:
    import asyncio

    if asyncio.iscoroutine(result):
        await result
