#!/usr/bin/env python3
"""Validate production environment before deploy or container start."""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxforge.config import Settings
from voxforge.infrastructure.security.production import collect_production_errors


def _load_env_file(path: Path) -> None:
    if not path.is_file():
        return
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def main() -> int:
    env_file = os.environ.get("ENV_FILE")
    if env_file:
        _load_env_file(Path(env_file))

    settings = Settings()
    errors = collect_production_errors(settings)
    if errors:
        print("Production environment validation failed:", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1
    print("Production environment validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
