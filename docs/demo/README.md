# Demo Documentation

Materials for demonstrating VoxForge to recruiters, investors, and pilot customers.

## Live demo

| URL | Purpose |
|-----|---------|
| https://voxforge.brohammad.tech | Product landing page |
| https://voxforge.brohammad.tech/demo | One-click voice pipeline |
| https://voxforge.brohammad.tech/dashboard | Operator console |

## Scripts

| Document | Duration | Audience |
|----------|----------|----------|
| [demo-script-short.md](demo-script-short.md) | 60 seconds | Social, quick intro |
| [demo-script-long.md](demo-script-long.md) | 8 minutes | Technical walkthrough |
| [presenter-notes.md](presenter-notes.md) | — | Talking points and FAQs |

## Recording

| Document | Purpose |
|----------|---------|
| [recording-checklist.md](recording-checklist.md) | Pre-flight, assets, ffmpeg GIF |

## Assets

| Asset | Location |
|-------|----------|
| Demo GIF | `docs/assets/screenshots/demo.gif` |
| Screenshots | `docs/assets/screenshots/` |

## Local demo

```bash
uvicorn voxforge.main:app --reload --app-dir src
# Open http://localhost:8000/demo
```

Mock providers — no API keys required when `DEMO_ENABLED=true`.
