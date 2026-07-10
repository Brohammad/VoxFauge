# ROI Calculator (Pilot)

Use this worksheet to estimate value for a design partner evaluation.

## Inputs

| Variable | Your value | Default |
|----------|------------|---------|
| Voice sessions / month | _____ | 10,000 |
| Avg handle time (min) | _____ | 4 |
| Agent hourly cost ($) | _____ | 25 |
| % automatable | _____ | 40% |
| Engineering weeks saved | _____ | 8 |
| Engineer cost ($/week) | _____ | 5,000 |

## Calculations

**Labor savings (monthly):**

```
sessions × handle_time × automatable × (hourly_cost / 60)
```

**Example:** 10,000 × 4 × 0.40 × (25/60) = **$6,667/month**

**Build cost avoidance:**

```
engineering_weeks_saved × engineer_cost
```

**Example:** 8 × $5,000 = **$40,000 one-time**

## VoxForge costs (self-hosted)

| Item | Est. monthly |
|------|--------------|
| VPS (4GB) | $24–48 |
| Voice API usage | Variable (BYO keys) |
| Engineering maintenance | 0.25 FTE |

## Net value (12 months)

```
(labor_savings × 12) + build_avoidance - (infra × 12) - maintenance
```

Document assumptions in your [case study](case-study-template.md).
