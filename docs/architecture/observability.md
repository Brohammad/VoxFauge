# Observability Stack

VoxForge ships with Prometheus and Grafana in Docker Compose for pipeline metrics.

## Services

| Service | URL | Credentials |
|---------|-----|-------------|
| VoxForge API | http://localhost:8000 | JWT / API key |
| Dashboard | http://localhost:8000/dashboard | JWT in connect bar |
| Prometheus | http://localhost:9090 | — |
| Grafana | http://localhost:3000 | admin / voxforge |

## Metrics scraped

Prometheus scrapes `/api/v1/metrics` from the app container every 15s.

Key panels in the bundled Grafana dashboard:

- E2E turn latency (p50)
- Active sessions and WebSocket connections
- Turns completed vs interrupted
- Evaluation score distribution
- Tool call rate by tool name
- Outcome KPI writes by intent/success/escalation
- Onboarding funnel step completions

## Quick start

```bash
docker compose up -d
# Migrations run automatically via scripts/docker-entrypoint.sh
```

Grafana auto-provisions the Prometheus datasource and VoxForge dashboard from `infra/grafana/`.
