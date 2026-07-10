"""Background worker for knowledge base ingestion jobs."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_ROOT))

from voxforge.config import get_settings
from voxforge.infrastructure.db.knowledge_repository import KnowledgeRepository
from voxforge.infrastructure.db.session import close_db, get_session_factory, init_db
from voxforge.infrastructure.knowledge.blob import create_blob_store
from voxforge.infrastructure.observability.logging import configure_logging, get_logger
from voxforge.infrastructure.providers.embeddings.factory import create_embedding_provider
from voxforge.modules.knowledge.application.ingestion_service import KnowledgeIngestionService

logger = get_logger(__name__)


async def run_worker() -> None:
    settings = get_settings()
    if not settings.knowledge_enabled:
        logger.warning("knowledge_worker_disabled")
        return

    await init_db(settings.database_url)
    factory = get_session_factory()
    blob = create_blob_store(settings.knowledge_blob_store, path=settings.knowledge_blob_path)
    poll = settings.knowledge_worker_poll_interval_sec

    logger.info("knowledge_worker_started", poll_interval_sec=poll)
    try:
        while True:
            async with factory() as session:
                repo = KnowledgeRepository(session)
                job = await repo.claim_next()
                if job is None:
                    await asyncio.sleep(poll)
                    continue
                ingestion = KnowledgeIngestionService(
                    repo,
                    blob,
                    create_embedding_provider(settings),
                    settings,
                )
                try:
                    await ingestion.process_job(job.id)
                    await session.commit()
                except Exception:
                    await session.rollback()
                    logger.exception("knowledge_worker_job_failed", job_id=str(job.id))
    finally:
        await close_db()


def main() -> None:
    configure_logging(get_settings().log_level)
    asyncio.run(run_worker())


if __name__ == "__main__":
    main()
