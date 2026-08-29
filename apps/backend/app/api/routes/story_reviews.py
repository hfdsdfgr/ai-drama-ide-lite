"""剧情一致性审核 API。"""

from fastapi import APIRouter, Request

from app.schemas.story_review import (
    ManualStoryReviewRequest,
    StoryReviewRunRequest,
    StoryDecisionRequest,
)

router = APIRouter(
    prefix="/api/projects/{project_id}/story-reviews",
    tags=["story-reviews"],
)


@router.post("/run", response_model=dict, status_code=201)
def run_model_review(
    project_id: str,
    payload: StoryReviewRunRequest,
    request: Request,
) -> dict:
    record = request.app.state.story_consistency_service.create_model_review_job(
        request.app.state.job_store,
        project_id,
        payload.shot_id,
        model_id=payload.model_id,
    )
    return _job_out(record)


@router.post("/manual", response_model=dict, status_code=201)
def submit_manual_review(
    project_id: str,
    payload: ManualStoryReviewRequest,
    request: Request,
) -> dict:
    return request.app.state.story_consistency_service.create_manual_review(
        project_id,
        payload.shot_id,
        consistent=payload.consistent,
        issue=payload.issue,
    )


@router.get("", response_model=list[dict])
def list_reviews(
    project_id: str,
    shot_id: str,
    request: Request,
) -> list[dict]:
    return request.app.state.story_consistency_service.reviews.list_for_shot(
        project_id, shot_id
    )


@router.post("/{review_id}/decision", response_model=dict)
def decide_review(
    project_id: str,
    review_id: str,
    payload: StoryDecisionRequest,
    request: Request,
) -> dict:
    return request.app.state.story_consistency_service.set_decision(
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
