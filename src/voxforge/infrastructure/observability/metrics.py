from prometheus_client import Counter, Gauge, Histogram

# Latency histograms
stt_latency_seconds = Histogram(
    "voxforge_stt_latency_seconds",
    "STT first partial transcript latency",
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0),
)

llm_first_token_seconds = Histogram(
    "voxforge_llm_first_token_seconds",
    "LLM time to first token",
    buckets=(0.1, 0.2, 0.3, 0.5, 0.75, 1.0, 2.0, 5.0),
)

tts_first_byte_seconds = Histogram(
    "voxforge_tts_first_byte_seconds",
    "TTS time to first audio byte",
    buckets=(0.05, 0.1, 0.2, 0.3, 0.5, 1.0, 2.0),
)

e2e_turn_latency_seconds = Histogram(
    "voxforge_e2e_turn_latency_seconds",
    "End-to-end turn latency (final transcript to first audio)",
    buckets=(0.5, 0.75, 1.0, 1.5, 2.0, 3.0, 5.0),
)

# Gauges
active_sessions = Gauge("voxforge_active_sessions", "Number of active voice sessions")
ws_connections = Gauge("voxforge_ws_connections", "Number of active WebSocket connections")

# Counters
turns_completed = Counter("voxforge_turns_completed_total", "Total conversation turns completed")
turns_interrupted = Counter(
    "voxforge_turns_interrupted_total",
    "Total turns interrupted by barge-in",
)
provider_errors = Counter(
    "voxforge_provider_errors_total",
    "Total provider errors",
    ["provider", "operation"],
)
tool_calls_total = Counter(
    "voxforge_tool_calls_total",
    "Total tool invocations",
    ["tool_name", "status"],
)
tool_latency_seconds = Histogram(
    "voxforge_tool_latency_seconds",
    "Tool execution latency",
    ["tool_name"],
    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 5.0, 30.0),
)
memory_stores_total = Counter(
    "voxforge_memory_stores_total",
    "Total memory entries stored",
)
memory_retrieval_latency_seconds = Histogram(
    "voxforge_memory_retrieval_latency_seconds",
    "Memory retrieval latency",
    buckets=(0.01, 0.05, 0.1, 0.2, 0.5, 1.0, 2.0),
)
evaluation_runs_total = Counter(
    "voxforge_evaluation_runs_total",
    "Total evaluation runs",
    ["status"],
)
evaluation_score_histogram = Histogram(
    "voxforge_evaluation_score",
    "Overall evaluation score per turn",
    buckets=(0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0),
)
outcome_records_total = Counter(
    "voxforge_outcome_records_total",
    "Total session outcome KPI records written",
    ["intent", "task_success", "escalation"],
)
outcome_resolution_seconds = Histogram(
    "voxforge_outcome_resolution_seconds",
    "Recorded resolution time for outcome KPIs",
    buckets=(5, 15, 30, 60, 120, 300, 600),
)
onboarding_steps_total = Counter(
    "voxforge_onboarding_steps_total",
    "Onboarding funnel step transitions",
    ["step", "status"],
)
