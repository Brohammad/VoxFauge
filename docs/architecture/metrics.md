# Metrics Catalog

Prometheus metrics exposed at `GET /api/v1/metrics`. All names use the `voxforge_` prefix.

Access is protected in production — see [Observability](./observability.md#metrics-access).

---

## Voice pipeline

| Metric | Type | Labels | When incremented |
|--------|------|--------|------------------|
| `voxforge_stt_latency_seconds` | Histogram | — | First partial STT result |
| `voxforge_llm_first_token_seconds` | Histogram | — | First LLM token per turn |
| `voxforge_tts_first_byte_seconds` | Histogram | — | First TTS audio byte |
| `voxforge_e2e_turn_latency_seconds` | Histogram | — | Final transcript → first audio |
| `voxforge_turns_completed_total` | Counter | — | Turn completes |
| `voxforge_turns_interrupted_total` | Counter | — | Barge-in interrupt |
| `voxforge_active_sessions` | Gauge | — | Active voice sessions |
| `voxforge_ws_connections` | Gauge | — | Open WebSocket connections |
| `voxforge_provider_errors_total` | Counter | `provider`, `operation` | STT/TTS/provider failures |

**Expected latency (p50 targets):** STT &lt;300ms, LLM first token &lt;500ms, TTS first byte &lt;300ms, E2E &lt;2s.

---

## Tools & MCP

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_tool_calls_total` | Counter | `tool_name`, `status` |
| `voxforge_tool_latency_seconds` | Histogram | `tool_name` |
| `voxforge_mcp_discovery_duration_seconds` | Histogram | — |
| `voxforge_mcp_servers_total` | Counter | `status` |

---

## Knowledge base

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_knowledge_ingest_jobs_total` | Counter | `status`, `source_type` |
| `voxforge_knowledge_ingest_duration_seconds` | Histogram | `stage` |
| `voxforge_knowledge_search_latency_seconds` | Histogram | — |
| `voxforge_knowledge_chunks_indexed_total` | Counter | — |

---

## Human handoff

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_handoff_initiated_total` | Counter | `trigger`, `org_id` |
| `voxforge_handoff_completed_total` | Counter | `status` |
| `voxforge_handoff_duration_seconds` | Histogram | `stage` |
| `voxforge_handoff_queue_depth` | Gauge | `org_id` |
| `voxforge_handoff_confidence_at_escalation` | Histogram | `trigger` |
| `voxforge_handoff_resume_total` | Counter | `status` |

**Intentionally not implemented:** `handoff_time_to_accept_seconds` and `handoff_time_to_resolve_seconds` (deferred — use `handoff_duration_seconds` stages instead).

---

## LiveKit

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_livekit_room_lifecycle_total` | Counter | `event` |
| `voxforge_livekit_participant_events_total` | Counter | `event` |
| `voxforge_livekit_barge_in_total` | Counter | — |
| `voxforge_livekit_reconnection_attempts_total` | Counter | — |
| `voxforge_livekit_dispatch_total` | Counter | `status` |
| `voxforge_livekit_audio_frame_latency_seconds` | Histogram | — |
| `voxforge_livekit_streaming_latency_seconds` | Histogram | — |

---

## Platform hardening

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_session_consistency_total` | Counter | `operation`, `outcome` |
| `voxforge_rate_limit_allowed_total` | Counter | `category`, `dimension` |
| `voxforge_rate_limit_blocked_total` | Counter | `category`, `dimension` |
| `voxforge_rate_limit_redis_errors_total` | Counter | `category`, `fail_mode` |
| `voxforge_integrity_violations_total` | Counter | `resource`, `operation` |
| `voxforge_duplicate_suppressed_total` | Counter | `resource` |

---

## Evaluation & outcomes

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_evaluation_runs_total` | Counter | `status` |
| `voxforge_evaluation_score` | Histogram | — |
| `voxforge_outcome_records_total` | Counter | `intent`, `task_success`, `escalation` |
| `voxforge_outcome_updates_total` | Counter | `intent` |
| `voxforge_outcome_resolution_seconds` | Histogram | — |
| `voxforge_onboarding_steps_total` | Counter | `step`, `status` |
| `voxforge_onboarding_sample_call_duration_seconds` | Histogram | — |
| `voxforge_regression_alerts_total` | Counter | `code`, `severity` |

---

## Memory

| Metric | Type | Labels |
|--------|------|--------|
| `voxforge_memory_stores_total` | Counter | — |
| `voxforge_memory_retrieval_latency_seconds` | Histogram | — |

---

## Cardinality guidance

- `org_id` appears only on handoff metrics where per-org queue depth is operationally required.
- Avoid adding high-cardinality labels (session_id, user_id, request_id) to Prometheus metrics.
- Use structured logs and traces for per-request attribution.
