"""项目级参考图库接口。"""

from pathlib import Path

from fastapi import APIRouter, File, Request, UploadFile
from fastapi.responses import FileResponse

from app.core.errors import AppError
from app.services.reference_media import ReferenceMediaRepository

router = APIRouter(prefix="/api/projects/{project_id}/references", tags=["references"])


def _out(project_id: str, item: dict, version) -> dict:
    return {
        "id": item["id"],
        "name": item["name"],
        "created_at": item["created_at"],
        "version": {
            "id": version.id,
            "entity_type": version.entity_type,
            "entity_id": version.entity_id,
            "version": version.version,
            "model_id": version.model_id,
            "provider_id": version.provider_id,
            "job_id": version.job_id,
            "payload": version.payload,
            "is_current": version.is_current,
            "created_at": version.created_at,
            "file_url": f"/api/projects/{project_id}/references/{item['id']}/file",
        },
    }


@router.get("")
def list_references(project_id: str, request: Request) -> list[dict]:
    repo = ReferenceMediaRepository(request.app.state.settings.db_path)
    versions = request.app.state.asset_version_service
    result = []
    for item in repo.list(project_id):
        current = versions.get_current(project_id, "reference_image", item["id"])
        if current:
            result.append(_out(project_id, item, current))
    return result


@router.post("/import", status_code=201)
async def import_reference(
    project_id: str, request: Request, file: UploadFile = File(...)
) -> dict:
    item, version = request.app.state.media_import_service.import_reference_image(
        project_id, file.filename or "", await file.read()
    )
    return _out(project_id, item, version)


@router.get("/{reference_id}/file")
def get_reference_file(project_id: str, reference_id: str, request: Request):
    item = ReferenceMediaRepository(request.app.state.settings.db_path).get(project_id, reference_id)
    record = request.app.state.asset_version_service.get_current(
        project_id, "reference_image", reference_id
    )
    if item is None or record is None or not Path(record.file_path).is_file():
        raise AppError(404, "reference_not_found", "参考图不存在")
    return FileResponse(record.file_path)
