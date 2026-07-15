# Operations Documentation

Day-2 guides for running VoxForge in production.

## Daily reference

| Document | When to use |
|----------|-------------|
| [runbook.md](runbook.md) | Status, logs, restart, smoke test |
| [../deployment/troubleshooting.md](../deployment/troubleshooting.md) | Something broke during deploy |
| [../deployment/recovery-guide.md](../deployment/recovery-guide.md) | Quick recovery procedures |
| [../deployment/rollback-guide.md](../deployment/rollback-guide.md) | Bad deploy or config change |

## Incidents & disasters

| Document | When to use |
|----------|-------------|
| [incident-response.md](incident-response.md) | P0/P1 outage — triage and communicate |
| [disaster-recovery.md](disaster-recovery.md) | Lost VPS or corrupted database |
| [backup-restore.md](backup-restore.md) | Scheduled backups and restore validation |

## Related deployment docs

| Document | Topic |
|----------|-------|
| [../deployment/operations.md](../deployment/operations.md) | Extended ops (scaling, secret rotation) |
| [../deployment/security.md](../deployment/security.md) | Security controls in production |
| [../deployment/verification-checklist.md](../deployment/verification-checklist.md) | Post-deploy QA |
| [../deployment/public-deployment-record.md](../deployment/public-deployment-record.md) | Reference live deployment |

## Quick commands

```bash
./deploy.sh status
./deploy.sh logs
./deploy.sh backup
./deploy.sh renew-cert
BASE_URL=https://your-domain ./scripts/smoke-test.sh
```

## SLA assumptions (self-hosted)

| Metric | Target |
|--------|--------|
| RPO | 24 hours (daily backups) |
| RTO | 2–4 hours (VPS reprovision + restore) |
| Uptime | Operator-managed — no hosted SLA |
