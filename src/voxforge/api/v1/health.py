from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import generate_latest

from voxforge.config import Settings, get_settings
from voxforge.infrastructure.observability.health import run_readiness_checks
from voxforge.infrastructure.observability.metrics_auth import require_metrics_access
from voxforge.infrastructure.tools.mcp_runtime_registry import MCPRuntimeRegistry

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok"}


@router.get("/ready")
async def ready(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> JSONResponse:
    mcp_registry: MCPRuntimeRegistry | None = getattr(request.app.state, "mcp_registry", None)
    report = await run_readiness_checks(settings, mcp_registry=mcp_registry)
    return JSONResponse(content=report.to_dict(), status_code=report.http_status)


@router.get("/metrics")
async def metrics(
    _: None = Depends(require_metrics_access),
) -> PlainTextResponse:
    return PlainTextResponse(
        content=generate_latest(),
        media_type="text/plain; version=0.0.4; charset=utf-8",
    )
