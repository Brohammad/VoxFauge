"""Unit tests for PostgreSQL pgvector SQL in MemoryRepository."""

from voxforge.infrastructure.db.memory_repository import _pgvector_literal


def test_pgvector_literal_format():
    assert _pgvector_literal([1.0, 0.0, 0.5]) == "[1.0,0.0,0.5]"


def test_search_sql_uses_cast_not_colon_cast():
    """asyncpg treats :name::type as invalid binding; queries must use CAST."""
    from pathlib import Path

    source = Path("src/voxforge/infrastructure/db/memory_repository.py").read_text()
    assert ":query_vec::vector" not in source
    assert ":vec::vector" not in source
    assert "CAST(:query_vec AS vector)" in source
    assert "CAST(:vec AS vector)" in source
