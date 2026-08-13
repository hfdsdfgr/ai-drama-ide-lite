"""Story Bible / 分析接口（Phase 6 — LLM Story Engine）。"""

from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.schemas.story import (
    AiChapterOut,
    AiChapterRequest,
    AiOutlineResult,
    AiOutlineRequest,
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


@router.post("/ai-outline", response_model=AiOutlineResult)
def ai_outline(
    project_id: str, payload: AiOutlineRequest, request: Request
) -> AiOutlineResult:
    return request.app.state.ai_novel_service.outline(
        project_id, payload.model_id, payload.brief
    )


@router.post("/ai-chapter", response_model=AiChapterOut)
def ai_chapter(project_id: str, payload: AiChapterRequest, request: Request) -> AiChapterOut:
    return request.app.state.ai_novel_service.chapter(
        project_id,
        payload.model_id,
        payload.brief,
        payload.outline,
        payload.chapter_index,
        payload.user_instruction,
        payload.previous_summaries,
    )
