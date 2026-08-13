"""Story Bible / 分析接口（Phase 6 — LLM Story Engine）。"""

import json

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

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


@router.post("/ai-chapter-stream")
def ai_chapter_stream(
    project_id: str, payload: AiChapterRequest, request: Request
) -> StreamingResponse:
    """SSE 流式章节生成：data: {"delta": "..."} ... data: {"done": true}。"""
    service = request.app.state.ai_novel_service

    def event_source():
        try:
            for delta in service.chapter_stream(
                project_id,
                payload.model_id,
                payload.brief,
                payload.outline,
                payload.chapter_index,
                payload.user_instruction,
                payload.previous_summaries,
            ):
                yield f"data: {json.dumps({'delta': delta}, ensure_ascii=False)}\n\n"
            yield f"data: {json.dumps({'done': True}, ensure_ascii=False)}\n\n"
        except Exception as exc:  # noqa: BLE001 - 错误以 SSE 事件返回，前端内联展示
            yield f"data: {json.dumps({'error': str(exc)}, ensure_ascii=False)}\n\n"

    return StreamingResponse(event_source(), media_type="text/event-stream")
