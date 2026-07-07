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
