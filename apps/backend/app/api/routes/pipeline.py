"""一键生产编排 API：计划（模型检查）/ 开始 / 状态。"""

from fastapi import APIRouter, Request

from app.schemas.pipeline import EpisodePipelinePlanOut, EpisodePipelineStartRequest, PipelineStartRequest

router = APIRouter(prefix="/api/projects/{project_id}/pipeline", tags=["pipeline"])


@router.get("/plan", response_model=dict)
def get_plan(project_id: str, request: Request) -> dict:
    return request.app.state.pipeline_service.plan(project_id)


@router.post("/start", response_model=dict, status_code=201)
def start_pipeline(
    project_id: str,
    payload: PipelineStartRequest,
    request: Request,
) -> dict:
    record = request.app.state.pipeline_service.start(
        request.app.state.job_store,
        project_id,
        auto_continue=payload.auto_continue,
        include_videos=payload.include_videos,
    )
    return _job_out(record)


@router.get("/status", response_model=dict)
def get_pipeline_status(project_id: str, request: Request) -> dict:
    return request.app.state.pipeline_service.status(project_id)


@router.get("/episodes/{episode_id}/plan", response_model=EpisodePipelinePlanOut)
def get_episode_plan(project_id: str, episode_id: str, request: Request) -> dict:
    return request.app.state.pipeline_service.plan_episode(project_id, episode_id)


@router.post("/episodes/{episode_id}/start", response_model=dict, status_code=201)
def start_episode_pipeline(
    project_id: str,
    episode_id: str,
    payload: EpisodePipelineStartRequest,
    request: Request,
) -> dict:
    record = request.app.state.pipeline_service.start_episode(
        request.app.state.job_store,
        project_id,
        episode_id,
        expected_config_revision=payload.expected_config_revision,
    )
    return _job_out(record)


@router.get("/episodes/{episode_id}/status", response_model=dict)
def get_episode_pipeline_status(
    project_id: str, episode_id: str, job_id: str, request: Request
) -> dict:
    return request.app.state.pipeline_service.status_episode(
        project_id, episode_id, job_id
    )


def _job_out(record) -> dict:
    extra = (record.input_payload or {}).get("extra") or {}
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
        "target_id": extra.get("target_id") or "",
        "target_type": extra.get("target_type") or "",
        "target_label": extra.get("target_label") or "",
        "created_at": record.created_at,
        "started_at": record.started_at,
        "completed_at": record.completed_at,
        "paused_at": record.paused_at,
        "cancelled_at": record.cancelled_at,
    }
