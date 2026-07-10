"""Structured log sanitization and trace context injection."""

from __future__ import annotations

import re
from typing import Any

# JWT-like tokens (header.payload.signature)
_JWT_PATTERN = re.compile(r"eyJ[A-Za-z0-9_-]+\.eyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+")
# VoxForge API keys
_API_KEY_PATTERN = re.compile(r"vxf_[A-Za-z0-9]{20,}")
# Bearer tokens in strings
_BEARER_PATTERN = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
# Generic long secrets in key=value patterns
_SECRET_KEY_PATTERN = re.compile(
    r"(password|secret|token|api_key|apikey|authorization)\s*[:=]\s*\S+",
    re.IGNORECASE,
)

_REDACTED = "[REDACTED]"


def _sanitize_string(value: str) -> str:
    if not value:
        return value
    result = _JWT_PATTERN.sub(_REDACTED, value)
    result = _API_KEY_PATTERN.sub(_REDACTED, result)
    result = _BEARER_PATTERN.sub(f"Bearer {_REDACTED}", result)
    result = _SECRET_KEY_PATTERN.sub(lambda m: f"{m.group(1)}={_REDACTED}", result)
    return result


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_string(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(item) for item in value]
    return value


def sanitize_log_event(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """structlog processor: redact sensitive values before JSON render."""
    return _sanitize_value(event_dict)


def inject_trace_context(
    _logger: Any,
    _method_name: str,
    event_dict: dict[str, Any],
) -> dict[str, Any]:
    """structlog processor: add trace_id/span_id from active OTel span."""
    try:
        from opentelemetry import trace

        span = trace.get_current_span()
        ctx = span.get_span_context()
        if ctx.is_valid:
            event_dict["trace_id"] = format(ctx.trace_id, "032x")
            event_dict["span_id"] = format(ctx.span_id, "016x")
    except Exception:
        pass
    return event_dict
