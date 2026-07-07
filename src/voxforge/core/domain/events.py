from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4


@dataclass
class TranscriptEvent:
    text: str
    is_partial: bool
    confidence: float | None = None
    language: str | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class TokenEvent:
    text: str
    is_final: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class AudioChunk:
    data: bytes
    sample_rate: int = 24000
    encoding: str = "pcm_s16le"
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class DomainEvent:
    event_id: UUID = field(default_factory=uuid4)
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))


@dataclass
class SessionCreated(DomainEvent):
    session_id: UUID = field(default_factory=uuid4)


@dataclass
class SessionResumed(DomainEvent):
    session_id: UUID = field(default_factory=uuid4)
    last_sequence: int = 0


@dataclass
class SessionEnded(DomainEvent):
    session_id: UUID = field(default_factory=uuid4)
    reason: str = "normal"


@dataclass
class InterruptReceived(DomainEvent):
    session_id: UUID = field(default_factory=uuid4)
