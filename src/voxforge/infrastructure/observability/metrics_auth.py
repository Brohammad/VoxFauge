"""Application-layer protection for the Prometheus /metrics endpoint."""

from __future__ import annotations

import ipaddress
from typing import Annotated

from fastapi import Depends, HTTPException, Request, Security
from fastapi.security import APIKeyHeader, HTTPAuthorizationCredentials, HTTPBearer

from voxforge.api.dependencies import get_auth_service
from voxforge.config import Settings, get_settings
from voxforge.core.domain.auth import Principal
from voxforge.core.exceptions import UnauthorizedError
from voxforge.modules.auth.application.service import AuthService

METRICS_SCOPE = "metrics:read"

_bearer_scheme = HTTPBearer(auto_error=False)
_api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    if request.client:
        return request.client.host
    return ""


def _ip_allowed(client_ip: str, allowed: tuple[str, ...]) -> bool:
    if not client_ip or not allowed:
        return False
    try:
        addr = ipaddress.ip_address(client_ip)
    except ValueError:
        return False
    for entry in allowed:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif addr == ipaddress.ip_address(entry):
                return True
        except ValueError:
            continue
    return False


def _principal_has_metrics_scope(principal: Principal) -> bool:
    return principal.has_scope(METRICS_SCOPE)


async def require_metrics_access(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(_bearer_scheme)],
    api_key: Annotated[str | None, Security(_api_key_header)],
    settings: Settings = Depends(get_settings),
    auth_service: AuthService = Depends(get_auth_service),
) -> None:
    """Authorize Prometheus scrape or operator access to /metrics."""
    if settings.metrics_allow_anonymous_effective:
        return

    client_ip = _client_ip(request)
    if _ip_allowed(client_ip, settings.metrics_allowed_ip_list):
        return

    token = credentials.credentials if credentials and credentials.credentials else None
    if settings.metrics_bearer_token and token == settings.metrics_bearer_token:
        return

    principal: Principal | None = None
    if token:
        try:
            principal = await auth_service.resolve_principal_from_bearer(token)
        except UnauthorizedError:
            principal = None

    if principal is None and api_key:
        try:
            principal = await auth_service.resolve_principal_from_api_key(api_key)
        except UnauthorizedError:
            principal = None

    if principal is not None and _principal_has_metrics_scope(principal):
        return

    raise HTTPException(status_code=401, detail="Metrics access requires authentication")
