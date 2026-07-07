from fastapi import APIRouter

from voxforge.api.v1.api_keys import router as api_keys_router
from voxforge.api.v1.auth import router as auth_router
from voxforge.api.v1.health import router as health_router
from voxforge.api.v1.orgs import router as orgs_router
from voxforge.api.v1.sessions import router as sessions_router

api_v1_router = APIRouter()
api_v1_router.include_router(health_router)
api_v1_router.include_router(auth_router)
api_v1_router.include_router(orgs_router)
api_v1_router.include_router(api_keys_router)
api_v1_router.include_router(sessions_router)
