import json
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from langgraph.graph import END, START, StateGraph

from voxforge.config import Settings
from voxforge.core.domain.agents import (
    CRITIC_PROMPT,
    EXECUTOR_PROMPT,
    PLANNER_PROMPT,
    SAFETY_PROMPT,
)


class OrchestratorState(TypedDict):
    messages: list[dict]
    user_input: str
    plan: str
    draft_response: str
    safety_passed: bool
    safety_reason: str
    critic_approved: bool
    critic_feedback: str
    final_response: str
    iteration: int
    agent_trace: Annotated[list[dict], lambda a, b: a + b]


def _to_lc_messages(messages: list[dict]) -> list[BaseMessage]:
    result: list[BaseMessage] = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")
        if role == "system":
            result.append(SystemMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        else:
            result.append(HumanMessage(content=content))
    return result


def _trace(agent: str, status: str, summary: str) -> list[dict]:
    return [{"agent": agent, "status": status, "summary": summary}]


def _parse_json(text: str) -> dict:
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def build_agent_graph(settings: Settings):
    planner_llm = ChatOpenAI(model=settings.planner_model, api_key=settings.openai_api_key)
    executor_llm = ChatOpenAI(model=settings.executor_model, api_key=settings.openai_api_key)
    critic_llm = ChatOpenAI(model=settings.critic_model, api_key=settings.openai_api_key)
    safety_llm = ChatOpenAI(model=settings.safety_model, api_key=settings.openai_api_key)

    async def planner(state: OrchestratorState) -> dict:
        history = _to_lc_messages(state["messages"])
        prompt = (
            f"{PLANNER_PROMPT}\n\nUser message: {state['user_input']}\n"
            f"Iteration: {state['iteration']}"
        )
        if state.get("critic_feedback"):
            prompt += f"\nCritic feedback to address: {state['critic_feedback']}"
        response = await planner_llm.ainvoke(history + [HumanMessage(content=prompt)])
        plan = response.content if isinstance(response.content, str) else str(response.content)
        return {
            "plan": plan,
            "agent_trace": _trace("planner", "completed", plan[:200]),
        }

    async def safety(state: OrchestratorState) -> dict:
        prompt = (
            f"{SAFETY_PROMPT}\n\nUser: {state['user_input']}\nPlan: {state.get('plan', '')}"
        )
        response = await safety_llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _parse_json(content)
        passed = bool(parsed.get("passed", True))
        reason = str(parsed.get("reason", ""))
        status = "completed" if passed else "blocked"
        result: dict = {
            "safety_passed": passed,
            "safety_reason": reason,
            "agent_trace": _trace("safety", status, reason or "passed"),
        }
        if not passed:
            result["final_response"] = (
                "I'm sorry, but I can't help with that request."
            )
        return result

    async def executor(state: OrchestratorState) -> dict:
        history = _to_lc_messages(state["messages"])
        prompt = (
            f"{EXECUTOR_PROMPT}\n\nPlan:\n{state.get('plan', '')}\n\n"
            f"User message: {state['user_input']}"
        )
        response = await executor_llm.ainvoke(history + [HumanMessage(content=prompt)])
        draft = response.content if isinstance(response.content, str) else str(response.content)
        return {
            "draft_response": draft,
            "agent_trace": _trace("executor", "completed", draft[:200]),
        }

    async def critic(state: OrchestratorState) -> dict:
        prompt = (
            f"{CRITIC_PROMPT}\n\nDraft response:\n{state.get('draft_response', '')}\n\n"
            f"User message: {state['user_input']}"
        )
        response = await critic_llm.ainvoke([HumanMessage(content=prompt)])
        content = response.content if isinstance(response.content, str) else str(response.content)
        parsed = _parse_json(content)
        approved = bool(parsed.get("approved", True))
        feedback = str(parsed.get("feedback", ""))
        return {
            "critic_approved": approved,
            "critic_feedback": feedback,
            "iteration": state["iteration"] + (0 if approved else 1),
            "agent_trace": _trace(
                "critic",
                "completed" if approved else "revised",
                feedback[:200] if feedback else "approved",
            ),
        }

    async def coordinator(state: OrchestratorState) -> dict:
        if state.get("final_response"):
            return {
                "agent_trace": _trace("coordinator", "blocked", state.get("safety_reason", "")),
            }
        final = state.get("draft_response", "")
        return {
            "final_response": final,
            "agent_trace": _trace("coordinator", "completed", final[:200]),
        }

    def route_after_safety(state: OrchestratorState) -> str:
        return "executor" if state.get("safety_passed", True) else "coordinator"

    def route_after_critic(state: OrchestratorState) -> str:
        if state.get("critic_approved", True):
            return "coordinator"
        if state.get("iteration", 0) >= settings.max_agent_iterations:
            return "coordinator"
        return "planner"

    graph = StateGraph(OrchestratorState)
    graph.add_node("planner", planner)
    graph.add_node("safety", safety)
    graph.add_node("executor", executor)
    graph.add_node("critic", critic)
    graph.add_node("coordinator", coordinator)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "safety")
    graph.add_conditional_edges("safety", route_after_safety, ["executor", "coordinator"])
    graph.add_edge("executor", "critic")
    graph.add_conditional_edges("critic", route_after_critic, ["coordinator", "planner"])
    graph.add_edge("coordinator", END)

    return graph.compile()
