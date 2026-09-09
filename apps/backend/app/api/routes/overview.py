"""Phase 15 — 项目生产阶段概览接口。"""

from fastapi import APIRouter, Request

from app.schemas.overview import (
    EpisodePrepareOut,
    EpisodeWorkspaceOut,
    ProjectOverviewOut,
)
from app.services.episode_workspace import build_episode_workspace, prepare_episode
from app.services.project_overview import build_project_overview


router = APIRouter(prefix="/api/projects/{project_id}/overview", tags=["overview"])


@router.get("", response_model=ProjectOverviewOut)
def get_overview(project_id: str, request: Request) -> dict:
    return build_project_overview(request.app.state.settings.db_path, project_id)


@router.get("/episodes", response_model=EpisodeWorkspaceOut)
def get_episode_workspace(project_id: str, request: Request) -> dict:
    return build_episode_workspace(request.app.state.settings.db_path, project_id)


@router.post("/episodes/{episode_id}/prepare", response_model=EpisodePrepareOut)
def run_episode_preflight(project_id: str, episode_id: str, request: Request) -> dict:
    return prepare_episode(request.app.state.settings.db_path, project_id, episode_id)
