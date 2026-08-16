"""Phase 15 — 项目生产阶段概览接口。"""

from fastapi import APIRouter, Request

from app.schemas.overview import ProjectOverviewOut
from app.services.project_overview import build_project_overview


router = APIRouter(prefix="/api/projects/{project_id}/overview", tags=["overview"])


@router.get("", response_model=ProjectOverviewOut)
def get_overview(project_id: str, request: Request) -> dict:
    return build_project_overview(request.app.state.settings.db_path, project_id)
