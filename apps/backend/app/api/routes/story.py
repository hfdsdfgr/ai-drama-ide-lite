"""Story Bible / 分析接口（Phase 6 — LLM Story Engine）。"""

from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.schemas.story import (
    AnalysisJobOut,
    AnalysisRequest,
    StoryBibleOut,
)
from app.services.story_repo import StoryRepository

router = APIRouter(prefix="/api/projects/{project_id}/story", tags=["story"])


@router.post("/analysis", response_model=AnalysisJobOut, status_code=201)
def start_analysis(
    project_id: str, payload: AnalysisRequest, request: Request
) -> dict:
    return request.app.state.story_service.start(
        project_id, payload.novel_id, payload.model_id, payload.mode
    )


@router.get("/analysis/{job_id}", response_model=AnalysisJobOut)
def get_analysis(project_id: str, job_id: str, request: Request) -> dict:
    job = request.app.state.story_service.get(job_id)
    if job.get("project_id") != project_id:
        raise AppError(404, "analysis_job_not_found", f"分析任务不存在: {job_id}")
    return job


@router.get("/bible", response_model=StoryBibleOut)
def get_bible(project_id: str, request: Request) -> dict:
    repo = StoryRepository(request.app.state.settings.db_path)
    return {"bible": repo.get_bible(project_id)}
