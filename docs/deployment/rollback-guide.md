# Rollback Guide

## Application rollback (code)

```bash
cd /opt/VoxForge
git fetch origin
git checkout <previous-tag-or-commit>
./deploy.sh up
```

Verify: `BASE_URL=https://voxforge.brohammad.tech ./scripts/smoke-test.sh`

## Database migration rollback

Alembic downgrade (use with caution):

```bash
docker compose -f docker-compose.prod.yml run --rm app \
  alembic downgrade -1
```

Prefer restore from backup if downgrade is risky.

## Configuration rollback

1. Restore previous `.env.production` from backup
2. `./deploy.sh up`
3. Verify readiness

## Agent config rollback

Use dashboard **Policy Presets → Config Version History** to activate a previous agent configuration version without redeploying code.

## When to rollback vs fix-forward

| Situation | Recommendation |
|-----------|----------------|
| Bad deploy, DB unchanged | Rollback code |
| Bad migration applied | Restore DB backup |
| Provider outage | Fix-forward (switch providers) |
| Security patch | Fix-forward |

## Rollback decision log

Document in GitHub issue:

- Commit rolled back from/to
- Reason
- Verification results
- Follow-up fix PR
