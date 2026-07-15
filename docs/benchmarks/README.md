# Benchmarks

Performance measurements and competitive positioning.

| Document | Description |
|----------|-------------|
| [onboarding.md](onboarding.md) | Local onboarding pipeline benchmarks |
| [knowledge-base.md](knowledge-base.md) | Knowledge search latency benchmarks |
| [competitive-analysis.md](competitive-analysis.md) | vs Vapi, Retell, LiveKit Agents, and others |

## Run locally

```bash
make benchmark-onboarding
make benchmark-knowledge-base
```

CI uploads benchmark artifacts on every push (non-blocking jobs).
