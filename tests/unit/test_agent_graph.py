"""Unit tests for LangGraph agent orchestrator graph helpers and routing."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from langchain_core.messages import AIMessage

from voxforge.config import Settings
from voxforge.modules.agent_orchestrator.application.graph import (
    _parse_json,
    _parse_uuid,
    _to_lc_messages,
    _trace,
    build_agent_graph,
)


class TestGraphHelpers:
    def test_to_lc_messages_roles(self):
        msgs = _to_lc_messages(
            [
                {"role": "system", "content": "sys"},
                {"role": "assistant", "content": "hi"},
                {"role": "user", "content": "hello"},
            ]
        )
        assert len(msgs) == 3
        assert msgs[0].content == "sys"
        assert msgs[1].content == "hi"
        assert msgs[2].content == "hello"

    def test_parse_json_plain(self):
        assert _parse_json('{"passed": true}') == {"passed": True}

    def test_parse_json_codeblock(self):
        raw = '```json\n{"approved": false, "feedback": "fix"}\n```'
        assert _parse_json(raw)["approved"] is False

    def test_parse_json_invalid_returns_empty(self):
        assert _parse_json("not json") == {}

    def test_parse_uuid_valid(self):
        uid = "00000000-0000-0000-0000-000000000001"
        assert str(_parse_uuid(uid)) == uid

    def test_parse_uuid_invalid(self):
        assert _parse_uuid("bad") is None
        assert _parse_uuid(None) is None

    def test_trace_format(self):
        t = _trace("planner", "completed", "plan text")
        assert t == [{"agent": "planner", "status": "completed", "summary": "plan text"}]


def _mock_llm_responses(*responses: AIMessage) -> MagicMock:
    mock_llm = MagicMock()
    mock_llm.ainvoke = AsyncMock(side_effect=list(responses))
    return mock_llm


@pytest.fixture
def graph_settings():
    return Settings(
        openai_api_key="test-key",
        tools_enabled=False,
        max_agent_iterations=2,
        max_tool_iterations=3,
    )


@pytest.mark.asyncio
async def test_graph_safety_block_short_circuits(graph_settings):
    mock_llm = _mock_llm_responses(
        AIMessage(content="Plan: help user"),
        AIMessage(content=json.dumps({"passed": False, "reason": "unsafe content"})),
    )

    with patch(
        "voxforge.modules.agent_orchestrator.application.graph.ChatOpenAI",
        return_value=mock_llm,
    ):
        graph = build_agent_graph(graph_settings)
        result = await graph.ainvoke(
            {
                "messages": [],
                "user_input": "harmful request",
                "plan": "",
                "draft_response": "",
                "safety_passed": True,
                "safety_reason": "",
                "critic_approved": True,
                "critic_feedback": "",
                "final_response": "",
                "iteration": 0,
                "session_id": None,
                "org_id": None,
                "caller_scopes": [],
                "agent_trace": [],
                "tool_calls": [],
            }
        )

    assert result["safety_passed"] is False
    assert "sorry" in result["final_response"].lower()
    trace_agents = [s["agent"] for s in result["agent_trace"]]
    assert "safety" in trace_agents
    assert "coordinator" in trace_agents


@pytest.mark.asyncio
async def test_graph_happy_path_without_tools(graph_settings):
    mock_llm = _mock_llm_responses(
        AIMessage(content="Plan: greet"),
        AIMessage(content=json.dumps({"passed": True, "reason": ""})),
        AIMessage(content="Hello! How can I help?"),
        AIMessage(content=json.dumps({"approved": True, "feedback": ""})),
    )

    with patch(
        "voxforge.modules.agent_orchestrator.application.graph.ChatOpenAI",
        return_value=mock_llm,
    ):
        graph = build_agent_graph(graph_settings)
        result = await graph.ainvoke(
            {
                "messages": [],
                "user_input": "Hi",
                "plan": "",
                "draft_response": "",
                "safety_passed": True,
                "safety_reason": "",
                "critic_approved": True,
                "critic_feedback": "",
                "final_response": "",
                "iteration": 0,
                "session_id": None,
                "org_id": None,
                "caller_scopes": [],
                "agent_trace": [],
                "tool_calls": [],
            }
        )

    assert result["final_response"] == "Hello! How can I help?"
    trace_agents = [s["agent"] for s in result["agent_trace"]]
    assert "planner" in trace_agents
    assert "executor" in trace_agents
    assert "critic" in trace_agents
    assert "coordinator" in trace_agents


@pytest.mark.asyncio
async def test_graph_critic_revision_loops_to_planner():
    graph_settings = Settings(
        openai_api_key="test-key",
        tools_enabled=False,
        max_agent_iterations=3,
        max_tool_iterations=1,
    )
    mock_llm = _mock_llm_responses(
        AIMessage(content="Plan v1"),
        AIMessage(content=json.dumps({"passed": True})),
        AIMessage(content="Draft v1"),
        AIMessage(content=json.dumps({"approved": False, "feedback": "too short"})),
        AIMessage(content="Plan v2"),
        AIMessage(content=json.dumps({"passed": True})),
        AIMessage(content="Draft v2 improved"),
        AIMessage(content=json.dumps({"approved": True, "feedback": ""})),
    )

    with patch(
        "voxforge.modules.agent_orchestrator.application.graph.ChatOpenAI",
        return_value=mock_llm,
    ):
        graph = build_agent_graph(graph_settings)
        result = await graph.ainvoke(
            {
                "messages": [],
                "user_input": "Explain refunds",
                "plan": "",
                "draft_response": "",
                "safety_passed": True,
                "safety_reason": "",
                "critic_approved": True,
                "critic_feedback": "",
                "final_response": "",
                "iteration": 0,
                "session_id": None,
                "org_id": None,
                "caller_scopes": [],
                "agent_trace": [],
                "tool_calls": [],
            }
        )

    assert "Draft v2" in result["final_response"]
    planner_steps = [s for s in result["agent_trace"] if s["agent"] == "planner"]
    assert len(planner_steps) >= 2
