"""Tests for security headers middleware."""

from voxforge.config import Settings
from voxforge.infrastructure.http.security_headers import SecurityHeadersMiddleware
from starlette.applications import Starlette
from starlette.responses import PlainTextResponse
from starlette.routing import Route
from starlette.testclient import TestClient


async def homepage(_request):
    return PlainTextResponse("ok")


def test_security_headers_added_in_development():
    app = Starlette(routes=[Route("/", homepage)])
    settings = Settings(app_env="development")
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    client = TestClient(app)
    response = client.get("/")
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert response.headers["X-Frame-Options"] == "DENY"
    assert "Strict-Transport-Security" not in response.headers


def test_security_headers_include_hsts_in_production():
    app = Starlette(routes=[Route("/", homepage)])
    settings = Settings(app_env="production")
    app.add_middleware(SecurityHeadersMiddleware, settings=settings)
    client = TestClient(app)
    response = client.get("/")
    assert "max-age=31536000" in response.headers["Strict-Transport-Security"]
