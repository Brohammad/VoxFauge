from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.entities import TransportType, TurnMetrics
from voxforge.infrastructure.db.models import OnboardingRunModel, SupportTemplateModel
from voxforge.infrastructure.db.outcome_repository import OutcomeRepository
from voxforge.infrastructure.observability.metrics import onboarding_steps_total
from voxforge.modules.outcomes.application.service import OutcomeExtractionService
from voxforge.modules.session_manager.application.service import SessionManager


class OnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._outcomes = OutcomeExtractionService(OutcomeRepository(db))

    async def start(self, org_id: UUID, user_id: UUID | None) -> OnboardingRunModel:
        run = OnboardingRunModel(
            org_id=org_id,
            created_by_user_id=user_id,
            status="started",
            metadata_={},
        )
        self._db.add(run)
        await self._db.flush()
        onboarding_steps_total.labels(step="start", status="started").inc()
        return run

    async def connect_token(
        self, org_id: UUID, user_id: UUID | None, token_preview: str | None = None
    ) -> OnboardingRunModel:
        run = await self._latest_run(org_id) or await self.start(org_id, user_id)
        run.status = "token_connected"
        run.connected_at = datetime.now(UTC)
        run.metadata_ = {**(run.metadata_ or {}), "token_preview": token_preview or ""}
        await self._db.flush()
        onboarding_steps_total.labels(step="connect_token", status="token_connected").inc()
        return run

    async def run_sample_call(
        self,
        org_id: UUID,
        user_id: UUID | None,
        session_manager: SessionManager,
    ) -> OnboardingRunModel:
        run = await self._latest_run(org_id) or await self.start(org_id, user_id)

        session = await session_manager.create_session(
            transport_type=TransportType.WEBSOCKET,
            config={"template_slug": "customer-support-deflection", "sample_call": True},
            org_id=org_id,
            created_by_user_id=user_id,
        )
        await session_manager.save_user_message(
            session.id,
            "Hi, I need help changing the billing contact on my account.",
            metadata={"intent": "billing_contact_change"},
        )
        await session_manager.save_assistant_message(
            session.id,
            "I can help with that. I verified your account and updated the billing contact.",
            metadata={"task_success": True},
        )
        await session_manager.save_turn_metrics(
            session.id,
            metrics=TurnMetrics(
                stt_ms=120.0,
                llm_first_token_ms=300.0,
                tts_first_byte_ms=180.0,
                e2e_ms=1450.0,
            ),
        )
        await session_manager.end_session(session.id, reason="onboarding_sample")

        await self._outcomes.record_outcome(
            org_id=org_id,
            session_id=session.id,
            user_transcript="Hi, I need help changing the billing contact on my account.",
            assistant_response=(
                "I can help with that. I verified your account "
                "and updated the billing contact."
            ),
            interrupted=False,
            resolution_time_seconds=95.0,
            user_metadata={"intent": "billing_contact_change"},
            assistant_metadata={"task_success": True},
        )
        run.status = "test_call_passed"
        run.test_session_id = session.id
        run.completed_at = datetime.now(UTC)
        run.metadata_ = {**(run.metadata_ or {}), "sample_call": "passed"}
        await self._db.flush()
        onboarding_steps_total.labels(step="run_sample_call", status="test_call_passed").inc()
        return run

    async def status(self, org_id: UUID) -> OnboardingRunModel | None:
        return await self._latest_run(org_id)

    async def get_default_template(self) -> SupportTemplateModel | None:
        result = await self._db.execute(
            select(SupportTemplateModel)
            .where(SupportTemplateModel.is_default.is_(True))
            .order_by(SupportTemplateModel.created_at.asc())
            .limit(1)
        )
        template = result.scalar_one_or_none()
        if template is not None:
            return template
        # Keep local/test environments functional even before migrations are applied.
        return SupportTemplateModel(
            name="Customer Support Deflection",
            slug="customer-support-deflection",
            prompt_config={
                "system_prompt": (
                    "You are a support voice agent focused on rapid resolution "
                    "and safe escalation."
                ),
                "style": "concise, empathetic, policy-safe",
            },
            tool_config={
                "enabled_tools": ["knowledge_base_lookup", "ticket_lookup", "ticket_create"],
                "fallback_to_human": True,
            },
            eval_thresholds={
                "task_success_min": 0.8,
                "quality_min": 0.75,
                "escalation_max": 0.35,
            },
            is_default=True,
        )

    async def _latest_run(self, org_id: UUID) -> OnboardingRunModel | None:
        result = await self._db.execute(
            select(OnboardingRunModel)
            .where(OnboardingRunModel.org_id == org_id)
            .order_by(OnboardingRunModel.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def commit(self) -> None:
        await self._db.commit()
