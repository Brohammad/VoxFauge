import time
from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from voxforge.core.domain.entities import TransportType
from voxforge.infrastructure.db.models import OnboardingRunModel, SupportTemplateModel
from voxforge.infrastructure.observability.logging import get_logger
from voxforge.infrastructure.observability.metrics import (
    onboarding_sample_call_duration_seconds,
    onboarding_steps_total,
)
from voxforge.infrastructure.observability.telemetry import get_tracer
from voxforge.modules.onboarding.application.sample_scripts import get_default_sample_script
from voxforge.modules.onboarding.ports.pipeline_runner import OnboardingPipelineRunner
from voxforge.modules.session_manager.application.service import SessionManager

logger = get_logger(__name__)
_tracer = get_tracer(__name__)


class OnboardingService:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db

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
        pipeline_runner: OnboardingPipelineRunner,
    ) -> OnboardingRunModel:
        run = await self._latest_run(org_id) or await self.start(org_id, user_id)
        script = get_default_sample_script()
        wall_start = time.monotonic()

        with _tracer.start_as_current_span("onboarding.sample_call") as span:
            span.set_attribute("voxforge.org_id", str(org_id))
            span.set_attribute("voxforge.script_id", script.script_id)

            session = await session_manager.create_session(
                transport_type=TransportType.WEBSOCKET,
                config={
                    "template_slug": "customer-support-deflection",
                    "sample_call": True,
                    "script_id": script.script_id,
                },
                org_id=org_id,
                created_by_user_id=user_id,
            )
            span.set_attribute("voxforge.session_id", str(session.id))

            try:
                metrics = await pipeline_runner.run_scripted_turn(
                    session_id=session.id,
                    org_id=org_id,
                    transcript=script.user_transcript,
                    user_metadata=script.user_metadata,
                )
                await session_manager.end_session(session.id, reason="onboarding_sample")

                run.status = "test_call_passed"
                run.test_session_id = session.id
                run.completed_at = datetime.now(UTC)
                run.metadata_ = {
                    **(run.metadata_ or {}),
                    "sample_call": "passed",
                    "script_id": script.script_id,
                    "e2e_ms": metrics.e2e_ms,
                }
                onboarding_steps_total.labels(
                    step="run_sample_call", status="test_call_passed"
                ).inc()
                logger.info(
                    "onboarding_sample_call_passed",
                    org_id=str(org_id),
                    session_id=str(session.id),
                    script_id=script.script_id,
                    e2e_ms=metrics.e2e_ms,
                )
            except Exception as exc:
                span.record_exception(exc)
                run.status = "test_call_failed"
                run.metadata_ = {
                    **(run.metadata_ or {}),
                    "sample_call": "failed",
                    "script_id": script.script_id,
                    "error": str(exc),
                }
                onboarding_steps_total.labels(
                    step="run_sample_call", status="test_call_failed"
                ).inc()
                logger.error(
                    "onboarding_sample_call_failed",
                    org_id=str(org_id),
                    session_id=str(session.id),
                    script_id=script.script_id,
                    error=str(exc),
                )
            finally:
                duration = time.monotonic() - wall_start
                onboarding_sample_call_duration_seconds.observe(duration)

            await self._db.flush()
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
