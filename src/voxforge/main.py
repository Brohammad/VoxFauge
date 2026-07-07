from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from voxforge.api.v1.router import api_v1_router
from voxforge.api.ws.voice import router as ws_router
from voxforge.config import get_settings
from voxforge.infrastructure.db.session import close_db, init_db
from voxforge.infrastructure.observability.logging import setup_logging
from voxforge.infrastructure.observability.telemetry import setup_telemetry
from voxforge.infrastructure.redis.client import close_redis, init_redis

DASHBOARD_DIR = Path(__file__).resolve().parents[2] / "dashboard"
LIVEKIT_EXAMPLE_DIR = Path(__file__).resolve().parents[2] / "examples" / "livekit-client"


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

    if DASHBOARD_DIR.is_dir():
        app.mount(
            "/dashboard/static",
            StaticFiles(directory=DASHBOARD_DIR / "static"),
            name="dashboard-static",
        )

        @app.get("/dashboard")
        async def dashboard_ui() -> FileResponse:
            return FileResponse(DASHBOARD_DIR / "index.html")

    if LIVEKIT_EXAMPLE_DIR.is_dir():
        app.mount(
            "/examples/livekit/static",
            StaticFiles(directory=LIVEKIT_EXAMPLE_DIR / "static"),
            name="livekit-example-static",
        )

        @app.get("/examples/livekit")
        async def livekit_example_ui() -> FileResponse:
            return FileResponse(LIVEKIT_EXAMPLE_DIR / "index.html")

    app.state.settings = settings
    return app


app = create_app()
