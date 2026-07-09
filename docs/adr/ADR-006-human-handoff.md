# ADR-006: Enterprise Human Handoff

## Status

Proposed (2026-07-10) — **pending review**

## Context

VoxForge has support tool primitives (`ticket_create`, `ticket_lookup`, `knowledge_base_lookup`), session persistence in Postgres, Redis streaming state, and post-hoc escalation labeling in `OutcomeExtractionService`. However:

- Escalation is **retrospective** — phrase matching and metadata flags after the turn, not runtime policy enforcement
- `fallback_to_human` in agent config presets is **stored but never read** at runtime
- `ticket_create` does not attach session context, conversation summary, or replay links
- No human agent queue, assignment, or resume flow exists
- Support tools only run in `ORCHESTRATOR_MODE=multi_agent` (not default `single`)
- Conversation state survives disconnect via `resume_session()`, but handoff has no defined state machine

Enterprise customers need governed escalation from four trigger types — confidence thresholds, tool failure, user request, and configurable policies — with a flow that creates a ticket, summarizes the conversation, generates a replay link, assigns a human, and resumes the session without losing context.

## Decision

Introduce a **Human Handoff module** with these architectural choices:

### 1. Central `HandoffOrchestrator` for the full flow

A single orchestrator coordinates:

1. **Create ticket** via existing `TicketingProvider` (extended with session context)
2. **Generate conversation summary** via `ConversationSummarizer` (LLM or extractive fallback)
3. **Generate replay link** via `ReplayLinkService` (signed token + `PUBLIC_BASE_URL`)
4. **Assign human** via new `AssignmentProvider` port
5. **Persist state** in `handoff_records` + `conversation_snapshots` + Redis handoff context

This replaces the pattern of agents calling `ticket_create` directly for escalations.

### 2. `HandoffPolicyEngine` evaluates triggers before response delivery

Per-turn evaluation in `VoicePipelineService` (post-evaluation, pre-TTS) combining:

| Trigger | Condition |
|---------|-----------|
| **Confidence threshold** | Composite score < `policy.min_confidence` |
| **Tool failure** | ERROR/TIMEOUT or consecutive failures ≥ `policy.max_tool_failures` |
| **User request** | `UserRequestDetector` matches transcript |
| **Escalation policy** | `policy.fallback_to_human=true` AND any trigger fires |

Policy loaded from active `agent_config_versions` or session `support_templates` config.

### 3. New `handoff_to_human` tool (replaces ad-hoc ticket_create for escalation)

Agent calls one tool; orchestrator handles the full package. `ticket_create` remains for non-escalation ticket creation (e.g., async follow-up).

### 4. Conversation state survival via layered persistence

| Layer | Mechanism |
|-------|-----------|
| **Postgres messages** | Authoritative transcript; never deleted on handoff |
| **`conversation_snapshots`** | Immutable freeze at handoff initiation |
| **`handoff_records`** | Links session ↔ ticket ↔ replay ↔ assignee |
| **Redis `SessionState`** | New phases `handoff_pending`, `handoff_active`; extended TTL |
| **Session resume** | Existing `resume_session()` + handoff context rehydration |

Session is **not ended** on handoff — status transitions to `handoff_pending` / `handoff_active`.

### 5. Database migration 011

Three new tables: `handoff_records`, `handoff_events`, `conversation_snapshots`. Extensions to `voice_sessions`, `tool_calls`, `outcome_kpis`.

### 6. Assignment via port (no vendor lock-in)

| Adapter | Use case |
|---------|----------|
| `MockAssignmentProvider` | Dev/test — assigns to fixed user |
| `RoundRobinAssignmentProvider` | v1 production — org member queue |
| Future: Zendesk/Freshdesk agent routing | External helpdesk integration |

### 7. Observability as first-class

Dedicated Prometheus metrics, OTel spans per handoff stage, `handoff` events in replay timeline, dashboard handoff queue panel.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| **Extend `ticket_create` only** | Does not handle summary, replay, assignment, or state machine |
| **External helpdesk-only handoff** | No conversation resume; vendor lock-in; replay link manual |
| **End session on handoff** | Loses resume capability; breaks WebSocket/LiveKit reconnect |
| **Celery for assignment queue** | Over-engineering; Postgres `handoff_records` status + polling sufficient for v1 |
| **Real-time human WebRTC bridge** | Out of scope; v1 uses same voice session transport with human agent API |
| **Phrase-only escalation (status quo)** | Not enterprise-grade; no policy governance or confidence thresholds |

## Consequences

**Positive**

- Unified escalation flow with audit trail (`handoff_events`)
- Conversation context packaged for human agents (summary + replay + ticket)
- Policy presets (`strict-compliance`, `high-touch-escalation`) become runtime-enforceable
- Evaluation scores directly drive escalation decisions
- Replay timeline includes handoff events for compliance review
- Idempotent handoff per session prevents duplicate tickets

**Negative / trade-offs**

- New session phases require WebSocket/LiveKit gateway updates
- `single` orchestrator mode needs policy-engine bypass or forced handoff injection
- Signed replay tokens add key management (`HANDOFF_REPLAY_SIGNING_SECRET`)
- Extended Redis TTL during handoff increases memory for long queue times
- Assignment routing is basic (round-robin) in v1 — skill-based queues deferred
- Migration adds foreign keys to `voice_sessions` — backfill needed for existing sessions

## Implementation phases

| Phase | Scope |
|-------|-------|
| **1** | Migration 011, domain models, `HandoffPolicyEngine`, unit tests |
| **2** | `HandoffOrchestrator`, replay links, `handoff_to_human` tool |
| **3** | Pipeline integration, Redis phase transitions, confidence composite |
| **4** | Human agent REST API, assignment provider, dashboard queue |
| **5** | External ticketing context, SLA alerts, Zendesk agent routing |

## Future migration

- Skill-based assignment queues per intent (billing, technical)
- Co-pilot mode (AI suggests, human approves)
- Warm transfer with context whisper to human agent
- Customer callback scheduling when no agents available
- Handoff analytics dashboard (CSAT post-handoff)

## References

- [Human Handoff Architecture](../architecture/human-handoff.md)
- [Customer Support Tools](../architecture/customer-support-tools.md)
- [Session Replay](../architecture/replay.md)
- [Outcomes](../architecture/outcomes.md)
- [ADR-005: Enterprise Knowledge Base](./ADR-005-enterprise-knowledge-base.md)
