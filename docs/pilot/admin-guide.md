# Admin Guide (Pilot)

Organization administrators manage users, API keys, SSO, and agent configuration.

## Initial setup

1. Register at `/dashboard` or use provided admin credentials
2. Create organization (automatic on first register)
3. Invite team members (register with same email domain or manual provisioning)

## API keys

1. Dashboard → generate API key (or `POST /api/v1/api-keys`)
2. Store securely — shown once
3. Use `Authorization: Bearer <api_key>` for programmatic access

## SAML SSO

1. Dashboard → **SSO** section
2. Create SAML connection with IdP metadata
3. Activate connection
4. Test SP-initiated login redirect

## Agent configuration

1. **Policy Presets** — apply bundled policies
2. **Config Version History** — rollback on regression
3. Environment variables override providers globally

## Security checklist

- [ ] Rotate `JWT_SECRET_KEY` from demo defaults
- [ ] Set strong `POSTGRES_PASSWORD`
- [ ] Enable `METRICS_BEARER_TOKEN` on 4GB+ VPS
- [ ] Set `DEMO_ENABLED=false` for production pilot
- [ ] Configure real voice providers (not mock)

## Backup

```bash
./deploy.sh backup
```

See [operations/backup-restore.md](../operations/backup-restore.md).
