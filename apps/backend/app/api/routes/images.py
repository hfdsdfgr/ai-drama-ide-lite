"""Phase 13 M2 - 项目级图片生成入口。"""

from pathlib import Path
from typing import Literal

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.schemas.asset_version import AssetVersionOut
from app.schemas.generation import GenerationJobOut
from app.schemas.image_generation import ImageGenerateRequest

router = APIRouter(prefix="/api/projects/{project_id}/images", tags=["images"])


@router.post("/generate", response_model=GenerationJobOut, status_code=201)
def generate_image(
    project_id: str,
    payload: ImageGenerateRequest,
    request: Request,
) -> dict:
    service = request.app.state.image_generation_service
    if payload.target_type == "asset":
        return service.start_asset(
            project_id,
            payload.target_id,
            payload.model_id,
            payload.capability,
            aspect_ratio=payload.aspect_ratio,
            art_style=payload.art_style,
            negative_prompt=payload.negative_prompt,
        )
    return service.start_shot(
        project_id,
        payload.target_id,
        payload.model_id,
        payload.capability,
        aspect_ratio=payload.aspect_ratio,
        art_style=payload.art_style,
        negative_prompt=payload.negative_prompt,
    )


@router.get("/jobs/{job_id}", response_model=GenerationJobOut)
def get_image_job(
    project_id: str,
    job_id: str,
    request: Request,
) -> dict:
    return request.app.state.image_generation_service.get_job(project_id, job_id)


@router.get("/versions", response_model=list[AssetVersionOut])
def list_image_versions(
    project_id: str,
    target_type: Literal["asset", "shot"],
    target_id: str,
    request: Request,
) -> list[dict]:
    entity_type = request.app.state.image_generation_service.resolve_entity_type(
        project_id, target_type, target_id
    )
    records = request.app.state.asset_version_service.list_versions(
        project_id, entity_type, target_id
    )
    return [_version_out(project_id, r) for r in records]


@router.get("/current", response_model=AssetVersionOut | None)
def get_current_image_version(
    project_id: str,
    target_type: Literal["asset", "shot"],
    target_id: str,
    request: Request,
) -> dict | None:
    entity_type = request.app.state.image_generation_service.resolve_entity_type(
        project_id, target_type, target_id
    )
    record = request.app.state.asset_version_service.get_current(
        project_id, entity_type, target_id
    )
    return _version_out(project_id, record) if record else None


@router.get("/versions/{version_id}/file")
def get_image_version_file(
    project_id: str,
    version_id: str,
    request: Request,
) -> FileResponse:
    record = request.app.state.asset_version_service.get(version_id)
    if record.project_id != project_id:
        raise AppError(404, "version_not_found", "图片版本不存在")
    path = Path(record.file_path)
    if not path.is_file():
        raise AppError(404, "version_file_not_found", "图片版本文件不存在")
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
        "file_url": f"/api/projects/{project_id}/images/versions/{record.id}/file",
    }
