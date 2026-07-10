# Pilot Success Metrics

## Primary KPIs (30-day pilot)

| Metric | Target | How to measure |
|--------|--------|----------------|
| Onboarding completion rate | ≥ 80% | Dashboard onboarding funnel |
| Median E2E latency | < 2s | `/api/v1/dashboard/latency` |
| Task success rate | ≥ 75% | Evaluation outcomes |
| Handoff rate | < 15% | Escalations / total sessions |
| Knowledge hit rate | ≥ 60% | Citations used / KB queries |

## Secondary KPIs

| Metric | Target |
|--------|--------|
| Uptime | 99.5% |
| P0 incidents | 0 |
| Time to first demo | < 15 min (new developer) |
| Operator replay usage | ≥ 1 replay/week |

## ROI framework

See [roi-calculator.md](roi-calculator.md).

**Value drivers:**

1. Reduced time to deploy voice agents (weeks → days)
2. Built-in evaluation vs custom instrumentation
3. Operator replay for QA and training
4. Self-hosted data control vs SaaS lock-in

## Reporting cadence

| Frequency | Deliverable |
|-----------|-------------|
| Weekly | KPI snapshot from dashboard |
| End of pilot | Completion report + case study draft |
