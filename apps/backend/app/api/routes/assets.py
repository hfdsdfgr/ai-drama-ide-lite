"""Phase 8 — 资产卡接口（Asset Engine）。"""

from fastapi import APIRouter, Request

from app.core.errors import AppError
from app.schemas.story import (
    AssetCardOut,
    AssetDeleteRequest,
    AssetGenerateJobOut,
    AssetGenerateRequest,
    AssetUpdateRequest,
)
from app.services.asset_service import ASSET_IMAGE_SPECS
from app.services.story_repo import ASSET_TYPES, StoryRepository

router = APIRouter(prefix="/api/projects/{project_id}/assets", tags=["assets"])


def _with_spec(asset: dict) -> dict:
    spec = ASSET_IMAGE_SPECS[asset["asset_type"]]
    return {
        "asset_type": asset["asset_type"],
        "asset_id": asset["asset_id"],
        "name": asset["name"],
        "image_spec": spec,
        "reference_prompt": asset["reference_prompt"],
        "fields": asset["fields"],
    }


@router.get("", response_model=list[AssetCardOut])
def list_assets(project_id: str, request: Request) -> list[dict]:
    repo = StoryRepository(request.app.state.settings.db_path)
    return [_with_spec(a) for a in repo.list_assets(project_id)]


@router.get("/specs")
def asset_specs(project_id: str) -> dict:
    return {"specs": ASSET_IMAGE_SPECS}


@router.put("", response_model=AssetCardOut)
def update_asset(
    project_id: str, payload: AssetUpdateRequest, request: Request
) -> dict:
    if payload.asset_type not in ASSET_TYPES:
        raise AppError(422, "invalid_asset_type", f"未知资产类型: {payload.asset_type}")
    repo = StoryRepository(request.app.state.settings.db_path)
    asset = repo.update_asset(
        project_id, payload.asset_type, payload.name, payload.patch
    )
    if asset is None:
        raise AppError(404, "asset_not_found", f"资产不存在: {payload.name}")
    return _with_spec(asset)


@router.delete("", status_code=204)
def delete_asset(
    project_id: str, payload: AssetDeleteRequest, request: Request
) -> None:
    if payload.asset_type not in ASSET_TYPES:
        raise AppError(422, "invalid_asset_type", f"未知资产类型: {payload.asset_type}")
    repo = StoryRepository(request.app.state.settings.db_path)
    if not repo.delete_asset(project_id, payload.asset_type, payload.name):
        raise AppError(404, "asset_not_found", f"资产不存在: {payload.name}")


@router.post("/generate", response_model=AssetGenerateJobOut, status_code=201)
def start_asset_generation(
    project_id: str, payload: AssetGenerateRequest, request: Request
) -> dict:
    return request.app.state.asset_service.start(project_id, payload.model_id)


@router.get("/generate/{job_id}", response_model=AssetGenerateJobOut)
def get_asset_generation(
    project_id: str, job_id: str, request: Request
) -> dict:
    job = request.app.state.asset_service.get(job_id)
    if job.get("project_id") != project_id:
        raise AppError(404, "asset_job_not_found", f"资产任务不存在: {job_id}")
    return job
