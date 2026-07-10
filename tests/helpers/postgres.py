"""PostgreSQL test helpers."""

import os
import subprocess
import sys

from voxforge.config import get_settings


def run_alembic_migrations() -> None:
    """Apply Alembic migrations to the database in DATABASE_URL."""
    env = os.environ.copy()
    env["DATABASE_URL"] = get_settings().database_url
    subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        check=True,
        env=env,
    )
