"""Redis-backed HTTP rate limiting for public endpoints."""

from __future__ import annotations

import time
from collections.abc import Callable

from fastapi import HTTPException, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from voxforge.config import Settings
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.redis.client import get_redis

logger = get_logger(__name__)


class RateLimitMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, settings: Settings) -> None:
        super().__init__(app)
        self._settings = settings
        self._prefixes = tuple(settings.rate_limit_path_prefixes)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        if not self._settings.rate_limit_enabled:
            return await call_next(request)

        path = request.url.path
        if not any(path.startswith(prefix) for prefix in self._prefixes):
            return await call_next(request)

        forwarded = request.headers.get("x-forwarded-for")
        if forwarded:
            client_ip = forwarded.split(",")[0].strip()
        elif request.client:
            client_ip = request.client.host
        else:
            client_ip = "unknown"

        bucket = int(time.time()) // 60
        key = f"ratelimit:{client_ip}:{path}:{bucket}"

        try:
            redis = get_redis()
            count = await redis.incr(key)
            if count == 1:
                await redis.expire(key, 70)
            if count > self._settings.rate_limit_per_minute:
                logger.warning("rate_limit_exceeded", path=path, client_ip=client_ip)
                raise HTTPException(
                    status_code=429,
                    detail="Rate limit exceeded. Try again shortly.",
                )
        except HTTPException:
            raise
        except Exception as exc:
            logger.warning("rate_limit_redis_error", error=str(exc))

        return await call_next(request)
