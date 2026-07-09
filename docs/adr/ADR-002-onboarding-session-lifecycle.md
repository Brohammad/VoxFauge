# ADR-002: Onboarding Session Lifecycle

## Status

Accepted (2026-07-10)

## Context

Onboarding sample calls need isolated sessions for replay, evaluation benchmarking, and
dashboard outcome trends. Reusing a single sample session would conflate metrics and make
before/after comparisons unreliable.

## Decision

Every `POST /onboarding/run-sample-call`:

1. Creates a **new** `VoiceSession` with `config.sample_call=true` and `script_id`.
2. Runs exactly one programmatic turn through `VoicePipelineService`.
3. Ends the session with reason `onboarding_sample`.
4. Updates the **latest** `OnboardingRun` record with `test_session_id` pointing to the new
   session (run row is reused; session is always new).

Failed pipeline runs set `OnboardingRun.status=test_call_failed` without raising HTTP 500,
so the dashboard can surface failure state.

## Alternatives Considered

| Alternative | Why not chosen |
|-------------|----------------|
| Reuse last sample session | Pollutes replay history and outcome trends |
| New onboarding run per sample call | Unnecessary funnel noise; status endpoint tracks latest run only |
| Return 500 on pipeline failure | Poor DX for guided onboarding UI |

## Consequences

- Dashboard outcome `total_sessions` increments per sample-call run (expected for benchmarking).
- `GET /onboarding/status` reflects the most recent sample session id.
- Multiple sample calls in one org produce independent replay timelines.

## Future Migration

- Optional `GET /onboarding/runs` history endpoint if product needs full funnel audit trail.
- Link onboarding runs to prompt/agent-config versions when sample calls use versioned configs.
