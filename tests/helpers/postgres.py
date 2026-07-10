"""PostgreSQL test helpers."""

from alembic.config import Config

from alembic import command
from voxforge.config import get_settings


def run_alembic_migrations() -> None:
    """Apply Alembic migrations to the database in DATABASE_URL."""
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", get_settings().database_url)
    command.upgrade(cfg, "head")
