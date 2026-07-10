from fastapi import WebSocket

from voxforge.config import Settings
from voxforge.core.domain.auth import OrgRole, Principal, PrincipalType
from voxforge.core.exceptions import ForbiddenError, UnauthorizedError
from voxforge.modules.auth.application.service import AuthService


async def resolve_ws_principal(
    websocket: WebSocket,
    auth_service: AuthService,
    settings: Settings,
    message: dict | None = None,
) -> Principal:
    if not settings.auth_required:
        if settings.app_env == "production":
            raise UnauthorizedError("AUTH_REQUIRED must be enabled in production")
        from uuid import UUID

        return Principal(
            type=PrincipalType.USER,
            user_id=UUID("00000000-0000-0000-0000-000000000001"),
            org_id=UUID("00000000-0000-0000-0000-000000000010"),
            role=OrgRole.OWNER,
        )

    token = _header_bearer(websocket) or (message or {}).get("token")
    api_key = websocket.headers.get("x-api-key") or (message or {}).get("api_key")

    if token:
        principal = await auth_service.resolve_principal_from_bearer(token)
    elif api_key:
        principal = await auth_service.resolve_principal_from_api_key(api_key)
    else:
        raise UnauthorizedError("Authentication required for WebSocket voice session")

    if not principal.has_scope("ws:connect"):
        raise ForbiddenError("Missing ws:connect scope")

    return principal


def _header_bearer(websocket: WebSocket) -> str | None:
    auth = websocket.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return None
