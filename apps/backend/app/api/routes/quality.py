"""项目级质量报告 API。"""

from fastapi import APIRouter, Request

from app.services.quality_service import build_project_quality

router = APIRouter(prefix="/api/projects/{project_id}/quality", tags=["quality"])


@router.get("", response_model=dict)
def get_quality(project_id: str, request: Request) -> dict:
    return build_project_quality(request.app.state.settings.db_path, project_id)
