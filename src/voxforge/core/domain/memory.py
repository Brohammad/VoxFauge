from datetime import datetime
from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, Field


class MemoryEntryType(StrEnum):
    TURN = "turn"
    SUMMARY = "summary"
    FACT = "fact"


class MemoryEntry(BaseModel):
    id: UUID
    org_id: UUID
    session_id: UUID
    role: str
    content: str
    entry_type: MemoryEntryType = MemoryEntryType.TURN
    message_id: UUID | None = None
    metadata: dict = Field(default_factory=dict)
    similarity: float | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class SessionSummary(BaseModel):
    session_id: UUID
    org_id: UUID
    summary: str
    message_count: int
    updated_at: datetime

    model_config = {"from_attributes": True}


class MemoryContext(BaseModel):
    """Assembled context injected before LLM calls."""

    summary: str | None = None
    relevant_entries: list[MemoryEntry] = Field(default_factory=list)
    recent_message_count: int = 0
