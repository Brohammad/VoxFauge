# VoxForge Deployment Documentation

| Document | Description |
|----------|-------------|
| [guide.md](./guide.md) | Step-by-step VPS deployment |
| [architecture.md](./architecture.md) | Production topology and data flow |
| [operations.md](./operations.md) | Day-2 operations, backups, renewals |
| [troubleshooting.md](./troubleshooting.md) | Common failures and fixes |
| [security.md](./security.md) | Security controls and assumptions |
| [production-checklist.md](./production-checklist.md) | Pre/post deploy checklist |
| [phase5-deliverables.md](./phase5-deliverables.md) | Phase 5 review summary |

## Phase 5 deliverables

After deploying to your VPS, record:

- **Public URL:** `https://<your-domain>/`
- **Demo URL:** `https://<your-domain>/demo`
- **Startup time:** measure from `docker compose up` to `/api/v1/ready` OK
- **Resource utilization:** `docker stats` after demo traffic

This repository ships deployment artifacts; the public URL is assigned when you run `./deploy.sh init` on your infrastructure.
