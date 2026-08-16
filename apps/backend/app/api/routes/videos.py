"""Phase 14 M1 - Shot image-to-video endpoints."""

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.schemas.asset_version import AssetVersionOut
from app.schemas.generation import GenerationJobOut
from app.schemas.video_generation import VideoGenerateRequest

router = APIRouter(prefix="/api/projects/{project_id}/videos", tags=["videos"])


@router.post("/generate", response_model=GenerationJobOut, status_code=201)
def generate_video(
    project_id: str,
    payload: VideoGenerateRequest,
    request: Request,
) -> dict:
    return request.app.state.video_generation_service.start_shot_video(
        project_id,
        payload.target_id,
        payload.model_id,
        payload.prompt,
        duration=payload.duration,
        aspect_ratio=payload.aspect_ratio,
    )


@router.get("/jobs/{job_id}", response_model=GenerationJobOut)
def get_video_job(
    project_id: str,
    job_id: str,
    request: Request,
) -> dict:
    return request.app.state.video_generation_service.get_job(project_id, job_id)


@router.get("/current", response_model=AssetVersionOut | None)
def get_current_video_version(
    project_id: str,
    shot_id: str,
    request: Request,
) -> dict | None:
    record = request.app.state.video_generation_service.get_current_version(
        project_id, shot_id
    )
    return _version_out(project_id, record) if record else None


@router.get("/versions/{version_id}/file")
def get_video_version_file(
    project_id: str,
    version_id: str,
    request: Request,
) -> FileResponse:
    record = request.app.state.asset_version_service.get(version_id)
    if record.project_id != project_id:
        raise AppError(404, "version_not_found", "视频版本不存在")
    path = Path(record.file_path)
    if not path.is_file():
        raise AppError(404, "version_file_not_found", "视频版本文件不存在")
    return FileResponse(path)


def _version_out(project_id: str, record) -> dict:
    return {
        "id": record.id,
        "entity_type": record.entity_type,
        "entity_id": record.entity_id,
        "version": record.version,
        "model_id": record.model_id,
        "provider_id": record.provider_id,
        "job_id": record.job_id,
        "payload": record.payload,
        "is_current": record.is_current,
        "created_at": record.created_at,
        "file_url": f"/api/projects/{project_id}/videos/versions/{record.id}/file",
    }
