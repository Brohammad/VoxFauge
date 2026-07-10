#!/usr/bin/env python3
"""Synchronize demo org, user, and password for hosted deployment."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from voxforge.config import Settings, get_settings
from voxforge.infrastructure.db.session import close_db, get_session_factory, init_db
from voxforge.infrastructure.demo.sync import ensure_demo_account


async def run(settings: Settings | None = None) -> None:
    settings = settings or get_settings()
    if not settings.demo_enabled:
        print("Demo account sync skipped (DEMO_ENABLED is not true).")
        return

    await init_db(settings.database_url)
    factory = get_session_factory()
    try:
        async with factory() as session:
            await ensure_demo_account(session, settings)
    finally:
        await close_db()

    print("Demo account synchronized.")


def main() -> int:
    try:
        asyncio.run(run())
    except Exception as exc:
        print(f"Demo account sync failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
