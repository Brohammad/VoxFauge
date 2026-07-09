"""Mock knowledge base and ticketing providers for development and demos."""

from __future__ import annotations

from datetime import UTC, datetime

from voxforge.core.domain.support import (
    KnowledgeArticle,
    KnowledgeSearchResult,
    SupportTicket,
    TicketCreateRequest,
)
from voxforge.core.interfaces.support import KnowledgeBaseProvider, TicketingProvider

_MOCK_ARTICLES: list[KnowledgeArticle] = [
    KnowledgeArticle(
        id="kb-001",
        title="How to reset your password",
        content=(
            "Go to Settings > Security > Reset Password. You will receive a verification "
            "email within 5 minutes. If you do not receive it, check spam or contact support."
        ),
        category="account",
        tags=["password", "security", "login"],
        url="https://help.voxforge.io/account/reset-password",
    ),
    KnowledgeArticle(
        id="kb-002",
        title="Billing and refund policy",
        content=(
            "Refunds are available within 30 days of purchase for annual plans. "
            "Monthly subscriptions can be cancelled anytime; partial refunds are not issued. "
            "Submit a ticket with your invoice ID for billing disputes."
        ),
        category="billing",
        tags=["billing", "refund", "invoice"],
        url="https://help.voxforge.io/billing/refunds",
    ),
    KnowledgeArticle(
        id="kb-003",
        title="Shipping delays and order tracking",
        content=(
            "Standard shipping takes 3-5 business days. Track your order in the portal "
            "using order ID. If tracking has not updated in 48 hours, open a support ticket "
            "with your order number."
        ),
        category="orders",
        tags=["shipping", "tracking", "delivery"],
        url="https://help.voxforge.io/orders/tracking",
    ),
    KnowledgeArticle(
        id="kb-004",
        title="Escalating to a human agent",
        content=(
            "If the voice agent cannot resolve your issue, ask to speak with a human. "
            "Your conversation context and ticket history will be passed to the support queue. "
            "Average wait time is under 5 minutes during business hours."
        ),
        category="support",
        tags=["handoff", "human", "escalation"],
        url="https://help.voxforge.io/support/handoff",
    ),
]

_MOCK_TICKETS: dict[str, SupportTicket] = {
    "TKT-1001": SupportTicket(
        id="TKT-1001",
        subject="Refund request for invoice INV-4421",
        description="Customer requested refund for duplicate annual charge.",
        status="open",
        priority="high",
        customer_email="customer@example.com",
        created_at=datetime(2026, 7, 8, 14, 30, tzinfo=UTC),
    ),
    "TKT-1002": SupportTicket(
        id="TKT-1002",
        subject="Order ORD-7782 not delivered",
        description="Tracking shows delivered but customer did not receive package.",
        status="pending",
        priority="normal",
        customer_email="customer@example.com",
        created_at=datetime(2026, 7, 9, 9, 15, tzinfo=UTC),
    ),
}


class MockKnowledgeBaseProvider:
    async def search(self, query: str, *, limit: int = 5) -> KnowledgeSearchResult:
        normalized = query.strip().lower()
        if not normalized:
            return KnowledgeSearchResult(query=query, articles=[], total=0)

        scored: list[tuple[int, KnowledgeArticle]] = []
        for article in _MOCK_ARTICLES:
            haystack = f"{article.title} {article.content} {' '.join(article.tags)}".lower()
            score = sum(1 for token in normalized.split() if token in haystack)
            if score:
                scored.append((score, article))

        scored.sort(key=lambda item: item[0], reverse=True)
        articles = [article for _, article in scored[:limit]]
        return KnowledgeSearchResult(query=query, articles=articles, total=len(articles))

    async def get_article(self, article_id: str) -> KnowledgeArticle | None:
        for article in _MOCK_ARTICLES:
            if article.id == article_id:
                return article
        return None


class MockTicketingProvider:
    def __init__(self) -> None:
        self._tickets = dict(_MOCK_TICKETS)
        self._counter = 1003

    async def lookup_ticket(self, ticket_id: str) -> SupportTicket | None:
        return self._tickets.get(ticket_id.strip().upper())

    async def lookup_by_customer_email(self, email: str, *, limit: int = 5) -> list[SupportTicket]:
        normalized = email.strip().lower()
        matches = [
            ticket
            for ticket in self._tickets.values()
            if ticket.customer_email and ticket.customer_email.lower() == normalized
        ]
        matches.sort(key=lambda t: t.created_at, reverse=True)
        return matches[:limit]

    async def create_ticket(self, request: TicketCreateRequest) -> SupportTicket:
        ticket_id = f"TKT-{self._counter}"
        self._counter += 1
        now = datetime.now(UTC)
        ticket = SupportTicket(
            id=ticket_id,
            subject=request.subject.strip(),
            description=request.description.strip(),
            status="open",
            priority=request.priority,
            customer_email=request.customer_email,
            created_at=now,
            updated_at=now,
        )
        self._tickets[ticket_id] = ticket
        return ticket
