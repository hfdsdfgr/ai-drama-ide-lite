"""Phase 9 — 资产版本接口：列表 / 当前 / 文件 / 恢复 / 删除。"""

from fastapi import APIRouter, Request
from fastapi.responses import FileResponse
from pathlib import Path

from app.core.errors import AppError
from app.schemas.asset_version import AssetVersionOut
from app.services.asset_version_service import AssetVersionRecord

router = APIRouter(
    prefix="/api/projects/{project_id}/assets/{asset_id}/versions",
    tags=["asset-versions"],
)


def _service(request: Request):
    return request.app.state.asset_version_service


def _out(project_id: str, asset_id: str, record: AssetVersionRecord) -> dict:
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
        "file_url": (
            f"/api/projects/{project_id}/assets/{asset_id}"
            f"/versions/{record.id}/file"
        ),
    }


def _check_owner(
    record: AssetVersionRecord, project_id: str, asset_id: str
) -> None:
    if record.project_id != project_id or record.entity_id != asset_id:
        raise AppError(404, "version_not_found", "资产版本不存在")


@router.get("", response_model=list[AssetVersionOut])
def list_versions(
    project_id: str,
    asset_id: str,
    request: Request,
) -> list[dict]:
    records = _service(request).list_versions(
        project_id, _asset_type(request, project_id, asset_id), asset_id
    )
    return [_out(project_id, asset_id, r) for r in records]


@router.get("/current", response_model=AssetVersionOut | None)
def get_current(
    project_id: str,
    asset_id: str,
    request: Request,
) -> dict | None:
    record = _service(request).get_current(
        project_id, _asset_type(request, project_id, asset_id), asset_id
    )
    return _out(project_id, asset_id, record) if record else None


@router.get("/{version_id}/file")
def get_version_file(
    project_id: str,
    asset_id: str,
    version_id: str,
    request: Request,
) -> FileResponse:
    record = _service(request).get(version_id)
    _check_owner(record, project_id, asset_id)
    path = Path(record.file_path)
    if not path.is_file():
        raise AppError(404, "version_file_not_found", "版本图片文件不存在")
    return FileResponse(path)


@router.post("/{version_id}/promote", response_model=AssetVersionOut)
def promote_version(
    project_id: str,
    asset_id: str,
    version_id: str,
    request: Request,
) -> dict:
    record = _service(request).get(version_id)
    _check_owner(record, project_id, asset_id)
    promoted = _service(request).promote(version_id)
    return _out(project_id, asset_id, promoted)


@router.delete("/{version_id}", status_code=204)
def delete_version(
    project_id: str,
    asset_id: str,
    version_id: str,
    request: Request,
) -> None:
    record = _service(request).get(version_id)
    _check_owner(record, project_id, asset_id)
    _service(request).delete(version_id)


def _asset_type(request: Request, project_id: str, asset_id: str) -> str:
    """从 assets 表解析资产类型（entity_type），不存在则 404。"""
    from app.db.database import get_connection

    with get_connection(request.app.state.settings.db_path) as conn:
        row = conn.execute(
            "SELECT asset_type FROM assets WHERE id = ? AND project_id = ?",
            (asset_id, project_id),
        ).fetchone()
    if row is None:
        raise AppError(404, "asset_not_found", f"资产不存在: {asset_id}")
    return row["asset_type"]
