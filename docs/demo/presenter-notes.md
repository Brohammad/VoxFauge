# Presenter Notes — VoxForge Demo

## Before you present

- Open tabs: landing, demo (pre-loaded), dashboard (logged in), GitHub README
- Run demo once to warm cache
- Know your audience: technical vs business

## Key messages by audience

| Audience | Emphasize |
|----------|-----------|
| Recruiter / HM | Live URL, tests, architecture, shipped product |
| CTO | Self-hosted, security, extensibility, no lock-in |
| Pilot customer | Time to value, replay, handoff, knowledge base |
| OSS contributor | CONTRIBUTING, good first issues, CI |

## Numbers to cite

- **354+** automated tests
- **81%** code coverage
- **36ms** demo E2E (mock providers)
- **15 min** clone to first demo
- **RC-1** live at voxforge.brohammad.tech

## Anticipated questions

**"Is the demo real voice?"**  
Mock providers in public demo; swap env vars for Deepgram/OpenAI/ElevenLabs in pilot.

**"How is this different from Vapi?"**  
Self-hosted, open source, evaluation/replay built in. See benchmark doc.

**"Can I use my own LLM?"**  
Yes — provider adapters via environment variables.

## If demo fails live

1. Show pre-captured screenshot in README
2. Walk through dashboard replay of last session
3. Show CI badge and test count on GitHub

## Close

- Star on GitHub
- Try `/demo`
- Open pilot request issue
