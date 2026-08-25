"""视觉一致性审核 API：模型审核 / 人工审核 / 结果与决策。"""

from fastapi import APIRouter, Request

from app.schemas.visual_review import (
    ManualVisualReviewRequest,
    VisualReviewRunRequest,
    VisualDecisionRequest,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/visual-reviews",
    tags=["visual-reviews"],
)


@router.post("/run", response_model=dict, status_code=201)
def run_model_review(
    project_id: str,
    payload: VisualReviewRunRequest,
    request: Request,
) -> dict:
    record = request.app.state.visual_review_service.create_model_review_job(
        request.app.state.job_store,
        project_id,
        payload.shot_id,
        model_id=payload.model_id,
        review_type=payload.review_type,
    )
    return _job_out(record)


@router.post("/manual", response_model=dict, status_code=201)
def submit_manual_review(
    project_id: str,
    payload: ManualVisualReviewRequest,
    request: Request,
) -> dict:
    return request.app.state.visual_review_service.create_manual_review(
        project_id,
        payload.shot_id,
        review_type=payload.review_type,
        consistent=payload.consistent,
        issue=payload.issue,
    )


@router.get("", response_model=list[dict])
def list_reviews(
    project_id: str,
    shot_id: str,
    request: Request,
) -> list[dict]:
    return request.app.state.visual_review_service.reviews.list_for_shot(
        project_id, shot_id
    )


@router.post("/{review_id}/decision", response_model=dict)
def decide_review(
    project_id: str,
    review_id: str,
    payload: VisualDecisionRequest,
    request: Request,
) -> dict:
    return request.app.state.visual_review_service.set_decision(
        project_id,
        review_id,
        decision=payload.decision,
    )


def _job_out(record) -> dict:
    return {
        "job_id": record.id,
        "project_id": record.project_id,
        "type": record.type,
        "status": record.status,
        "progress": record.progress,
        "model_id": record.model_id,
        "provider_id": record.provider_id,
        "capability": record.capability,
        "error": record.error or None,
        "error_category": record.error_category,
        "attempts": record.attempts,
        "result": record.result_payload if record.result_payload else None,
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "paused_at": record.paused_at,
        "cancelled_at": record.cancelled_at,
    }
