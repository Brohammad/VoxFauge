from fastapi import APIRouter

from voxforge.api.v1.health import router as health_router
from voxforge.api.v1.sessions import router as sessions_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(sessions_router)
