from fastapi import APIRouter

from voxforge.api.v1.agent_configs import router as agent_configs_router
from voxforge.api.v1.api_keys import router as api_keys_router
from voxforge.api.v1.auth import router as auth_router
from voxforge.api.v1.dashboard import router as dashboard_router
from voxforge.api.v1.demo import router as demo_router
from voxforge.api.v1.evaluations import router as evaluations_router
from voxforge.api.v1.handoffs import router as handoffs_router
from voxforge.api.v1.health import router as health_router
from voxforge.api.v1.knowledge import router as knowledge_router
from voxforge.api.v1.livekit import router as livekit_router
from voxforge.api.v1.memory import router as memory_router
from voxforge.api.v1.onboarding import router as onboarding_router
from voxforge.api.v1.orgs import router as orgs_router
from voxforge.api.v1.replay import router as replay_router
from voxforge.api.v1.sessions import router as sessions_router
from voxforge.api.v1.sso import router as sso_router
from voxforge.api.v1.templates import router as templates_router
from voxforge.api.v1.tools import router as tools_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(orgs_router)
api_v1_router.include_router(api_keys_router)
api_v1_router.include_router(sessions_router)
api_v1_router.include_router(replay_router)
api_v1_router.include_router(sso_router)
api_v1_router.include_router(livekit_router)
api_v1_router.include_router(memory_router)
api_v1_router.include_router(knowledge_router)
api_v1_router.include_router(handoffs_router)
api_v1_router.include_router(onboarding_router)
api_v1_router.include_router(templates_router)
api_v1_router.include_router(agent_configs_router)
api_v1_router.include_router(tools_router)
api_v1_router.include_router(evaluations_router)
api_v1_router.include_router(dashboard_router)
api_v1_router.include_router(demo_router)
