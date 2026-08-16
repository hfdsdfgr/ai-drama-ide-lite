"""Phase 14 M1 - Shot image-to-video endpoints."""

import uuid
from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.schemas.asset_version import AssetVersionOut
from app.schemas.generation import GenerationJobOut
from app.schemas.job import JobOut
from app.schemas.video_generation import AudioDubRequest, VideoGenerateRequest

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
        with_audio=payload.with_audio,
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


@router.post("/{shot_id}/dub", response_model=JobOut, status_code=201)
def dub_shot(
    project_id: str,
    shot_id: str,
    payload: AudioDubRequest,
    request: Request,
) -> dict:
    record = request.app.state.audio_dubbing_service.create_job(
        request.app.state.job_store,
        project_id,
        shot_id,
        voice_model_id=payload.voice_model_id,
        script_model_id=payload.script_model_id,
        voice=payload.voice,
        bgm_path=payload.bgm_path,
    )
    return _job_out(record)


@router.post("/audio-files", status_code=201)
async def upload_audio_file(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),
) -> dict:
    """上传本地音频文件（音效 / BGM），返回给配音 Job 使用的本地路径。"""
    filename = file.filename or ""
    ext = Path(filename).suffix.lstrip(".").lower() or "mp3"
    if ext not in {"mp3", "wav", "m4a", "aac", "flac", "ogg", "webm", "opus"}:
        raise AppError(422, "invalid_audio_type", "请上传常见音频文件（mp3 / wav / m4a / flac 等）")
    dest_dir = request.app.state.settings.projects_dir / project_id / "audio_uploads"
    dest_dir.mkdir(parents=True, exist_ok=True)
    target = dest_dir / f"audio_{uuid.uuid4().hex[:12]}.{ext}"
    target.write_bytes(await file.read())
    return {"file_path": str(target), "file_name": filename}


@router.get("/voiced/current", response_model=AssetVersionOut | None)
def get_current_voiced_version(
    project_id: str,
    shot_id: str,
    request: Request,
) -> dict | None:
    record = request.app.state.asset_version_service.get_current(
        project_id, "shot_video_voiced", shot_id
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
