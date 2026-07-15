# Rename remote to VoxForge

Docs and badges already point at `Brohammad/VoxForge`. If the GitHub repo is still named `VoxFauge`, rename it once:

```bash
gh repo rename VoxForge --repo Brohammad/VoxFauge --yes
git remote set-url origin https://github.com/Brohammad/VoxForge.git
```

GitHub keeps redirects from the old name for clones and stars.
