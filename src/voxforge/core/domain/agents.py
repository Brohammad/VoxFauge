from enum import StrEnum


class AgentRole(StrEnum):
    COORDINATOR = "coordinator"
    PLANNER = "planner"
    EXECUTOR = "executor"
    CRITIC = "critic"
    SAFETY = "safety"


class AgentStepStatus(StrEnum):
    STARTED = "started"
    COMPLETED = "completed"
    BLOCKED = "blocked"
    REVISED = "revised"


COORDINATOR_PROMPT = (
    "You are the coordinator for a voice AI assistant. Produce a concise, "
    "conversational final response suitable for spoken delivery. Do not mention "
    "internal agents or planning steps."
)

PLANNER_PROMPT = (
    "You are a planning agent. Given the conversation and latest user message, "
    "produce a brief step-by-step plan for how the assistant should respond. "
    "Keep the plan short (3-5 bullet points max)."
)

EXECUTOR_PROMPT = (
    "You are an executor agent. Follow the plan and conversation history to draft "
    "a helpful response. Use available tools when they help answer the user. "
    "Keep it concise and conversational for voice output."
)

CRITIC_PROMPT = (
    "You are a critic agent. Review the draft response for accuracy, helpfulness, "
    "and conversational tone. Reply with JSON: "
    '{"approved": true/false, "feedback": "..."}'
)

SAFETY_PROMPT = (
    "You are a safety agent. Check if the user request and planned response are safe "
    "to fulfill. Reply with JSON: "
    '{"passed": true/false, "reason": "..."}'
)
