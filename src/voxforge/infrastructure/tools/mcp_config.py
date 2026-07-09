import json
from typing import Any

from voxforge.infrastructure.observability.logging import get_logger

logger = get_logger(__name__)


def parse_mcp_servers_config(servers_config: str) -> list[dict[str, Any]]:
    if not servers_config.strip():
        return []
    try:
        parsed = json.loads(servers_config)
    except json.JSONDecodeError:
        logger.warning("mcp_config_invalid_json")
        return []
    if isinstance(parsed, list):
        return parsed
    if isinstance(parsed, dict):
        return [parsed]
    logger.warning("mcp_config_invalid_shape")
    return []


def server_id_for(server: dict[str, Any], index: int) -> str:
    explicit = server.get("id") or server.get("name")
    if isinstance(explicit, str) and explicit.strip():
        return explicit.strip()
    command = server.get("command", "server")
    return f"{command}-{index}"


def server_display_name(server: dict[str, Any], server_id: str) -> str:
    name = server.get("name")
    if isinstance(name, str) and name.strip():
        return name.strip()
    return server_id
