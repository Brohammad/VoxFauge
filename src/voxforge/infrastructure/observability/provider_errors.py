"""Shared provider error recording for Prometheus."""

from __future__ import annotations

from voxforge.infrastructure.observability.metrics import provider_errors


def record_provider_error(provider: str, operation: str) -> None:
    provider_errors.labels(provider=provider, operation=operation).inc()
