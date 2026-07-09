"""LiveKit room naming and session correlation helpers."""

from __future__ import annotations

from uuid import UUID

ROOM_PREFIX = "voxforge-"


def room_name_for_session(session_id: UUID) -> str:
    return f"{ROOM_PREFIX}{session_id}"


def parse_session_id(room_name: str) -> UUID:
    if not room_name.startswith(ROOM_PREFIX):
        raise ValueError(f"room name must start with {ROOM_PREFIX!r}")
    return UUID(room_name.removeprefix(ROOM_PREFIX))
