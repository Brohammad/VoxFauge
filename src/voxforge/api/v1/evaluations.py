from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel

from voxforge.api.dependencies import get_evaluation_engine, get_session_manager, require_scope
from voxforge.core.domain.auth import Principal
from voxforge.core.domain.evaluation import EvaluationRun
from voxforge.core.exceptions import SessionNotFoundError
from voxforge.modules.evaluation.application.service import EvaluationEngine
from voxforge.modules.session_manager.application.service import SessionManager

router = APIRouter(tags=["evaluations"])


class EvaluationMetricResponse(BaseModel):
    name: str
    score: float
    value: float | None
    unit: str | None
    status: str
    details: dict


class EvaluationRunResponse(BaseModel):
    id: UUID
    session_id: UUID
    user_transcript: str
    assistant_response: str
    overall_score: float
    overall_status: str
    metrics: list[EvaluationMetricResponse]
    created_at: str


class EvaluationListResponse(BaseModel):
    evaluations: list[EvaluationRunResponse]
    offset: int
    limit: int


@router.get("/sessions/{session_id}/evaluations", response_model=EvaluationListResponse)
async def list_session_evaluations(
    session_id: UUID,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    principal: Principal = Depends(require_scope("sessions:read")),
    session_manager: SessionManager = Depends(get_session_manager),
    evaluation_engine: EvaluationEngine | None = Depends(get_evaluation_engine),
) -> EvaluationListResponse:
    if evaluation_engine is None:
        raise HTTPException(status_code=503, detail="Evaluation engine is disabled")

    try:
        await session_manager.get_session(session_id, org_id=principal.org_id)
        runs = await evaluation_engine.list_for_session(
            session_id, org_id=principal.org_id, offset=offset, limit=limit
        )
    except SessionNotFoundError:
        raise HTTPException(status_code=404, detail="Session not found") from None

    return EvaluationListResponse(
        evaluations=[_run_to_response(r) for r in runs],
        offset=offset,
        limit=limit,
    )


@router.get("/evaluations/{run_id}", response_model=EvaluationRunResponse)
async def get_evaluation(
    run_id: UUID,
    principal: Principal = Depends(require_scope("sessions:read")),
    evaluation_engine: EvaluationEngine | None = Depends(get_evaluation_engine),
) -> EvaluationRunResponse:
    if evaluation_engine is None:
        raise HTTPException(status_code=503, detail="Evaluation engine is disabled")

    run = await evaluation_engine.get_run(run_id)
    if run.org_id is not None and run.org_id != principal.org_id:
        raise HTTPException(status_code=404, detail="Evaluation not found")
    return _run_to_response(run)


def _run_to_response(run: EvaluationRun) -> EvaluationRunResponse:
    return EvaluationRunResponse(
        id=run.id,
        session_id=run.session_id,
        user_transcript=run.user_transcript,
        assistant_response=run.assistant_response,
        overall_score=run.overall_score,
        overall_status=run.overall_status.value,
        metrics=[
            EvaluationMetricResponse(
                name=m.name.value,
                score=m.score,
                value=m.value,
                unit=m.unit,
                status=m.status.value,
                details=m.details,
            )
            for m in run.metrics
        ],
        created_at=run.created_at.isoformat(),
    )
