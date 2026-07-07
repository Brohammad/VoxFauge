from voxforge.config import Settings
from voxforge.core.interfaces.response_generator import ResponseGenerator
from voxforge.infrastructure.providers.llm.openai import OpenAILLMProvider
from voxforge.modules.agent_orchestrator.application.service import AgentOrchestrator
from voxforge.modules.conversation.application.engine import ConversationEngine


def create_response_generator(
    settings: Settings, llm: OpenAILLMProvider | None = None
) -> ResponseGenerator:
    if settings.orchestrator_mode == "multi_agent":
        return AgentOrchestrator(settings)
    if llm is None:
        llm = OpenAILLMProvider(settings.openai_api_key)
    return ConversationEngine(llm, settings)
