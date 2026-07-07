from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from voxforge.api.v1.router import api_v1_router
from voxforge.api.ws.voice import router as ws_router
from voxforge.config import get_settings
from voxforge.infrastructure.db.session import close_db, init_db
from voxforge.infrastructure.observability.logging import setup_logging
from voxforge.infrastructure.observability.telemetry import setup_telemetry
from voxforge.infrastructure.redis.client import close_redis, init_redis


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    settings = get_settings()
    setup_logging(settings.log_level)
    setup_telemetry(settings)
    await init_db(settings.database_url)
    await init_redis(settings.redis_url)
    yield
    await close_redis()
    await close_db()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="VoxForge",
        description="Production-grade Voice AI Infrastructure Platform",
        version="0.1.0",
        docs_url="/api/v1/docs",
        redoc_url="/api/v1/redoc",
        openapi_url="/api/v1/openapi.json",
        lifespan=lifespan,
    )
    app.include_router(api_v1_router, prefix="/api/v1")
    app.include_router(ws_router)
    app.state.settings = settings
    return app


app = create_app()
