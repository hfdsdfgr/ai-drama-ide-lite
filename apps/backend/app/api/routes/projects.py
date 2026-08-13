"""Project endpoints (Phase 0 minimal: create / save / reopen)."""

from fastapi import APIRouter, Request

from app.schemas.project import Project, ProjectCreate, ProjectUpdate
from app.services.project_store import ProjectStore

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _store(request: Request) -> ProjectStore:
    return ProjectStore(request.app.state.settings.projects_dir)


@router.get("", response_model=list[Project])
def list_projects(request: Request) -> list[Project]:
    return _store(request).list()


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate, request: Request) -> Project:
    return _store(request).create(payload)


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, request: Request) -> Project:
    return _store(request).get(project_id)


@router.put("/{project_id}", response_model=Project)
def update_project(
    project_id: str, payload: ProjectUpdate, request: Request
) -> Project:
    return _store(request).update(project_id, payload)
