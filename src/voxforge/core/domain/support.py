"""Domain models for customer support integrations."""

from datetime import datetime

from pydantic import BaseModel, Field


class KnowledgeArticle(BaseModel):
    id: str
    title: str
    content: str
    category: str
    tags: list[str] = Field(default_factory=list)
    url: str | None = None


class KnowledgeSearchResult(BaseModel):
    query: str
    articles: list[KnowledgeArticle] = Field(default_factory=list)
    total: int = 0


class SupportTicket(BaseModel):
    id: str
    subject: str
    description: str
    status: str  # open | pending | resolved | closed
    priority: str  # low | normal | high | urgent
    customer_email: str | None = None
    created_at: datetime
    updated_at: datetime | None = None


class TicketCreateRequest(BaseModel):
    subject: str
    description: str
    customer_email: str | None = None
    priority: str = "normal"
