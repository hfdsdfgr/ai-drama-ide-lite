"""Project endpoints：CRUD + 导入导出（Phase 1）。"""

from fastapi import APIRouter, Request, Response

from app.core.errors import AppError
from app.schemas.project import Project, ProjectCreate, ProjectUpdate
from app.services.project_repo import ProjectRepository
from app.services.project_transfer import export_project_zip, import_project_zip

router = APIRouter(prefix="/api/projects", tags=["projects"])


def _repo(request: Request) -> ProjectRepository:
    settings = request.app.state.settings
    return ProjectRepository(settings.db_path, settings.projects_dir)


@router.get("", response_model=list[Project])
def list_projects(request: Request) -> list[Project]:
    return _repo(request).list()


@router.post("", response_model=Project, status_code=201)
def create_project(payload: ProjectCreate, request: Request) -> Project:
    return _repo(request).create(payload)


@router.post("/import", response_model=Project, status_code=201)
async def import_project(request: Request) -> Project:
    body = await request.body()
    if not body:
        raise AppError(422, "import_empty", "zip 内容为空")
    return import_project_zip(body, _repo(request))


@router.get("/{project_id}", response_model=Project)
def get_project(project_id: str, request: Request) -> Project:
    return _repo(request).get(project_id)


@router.put("/{project_id}", response_model=Project)
def update_project(
    project_id: str, payload: ProjectUpdate, request: Request
) -> Project:
    return _repo(request).update(project_id, payload)


@router.delete("/{project_id}", status_code=204)
def delete_project(project_id: str, request: Request) -> Response:
    _repo(request).soft_delete(project_id)
    return Response(status_code=204)


@router.get("/{project_id}/export")
def export_project(project_id: str, request: Request) -> Response:
    repo = _repo(request)
    project = repo.get(project_id)
    content = export_project_zip(project, repo.projects_dir / project.id)
    return Response(
        content=content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="project-{project.id}.zip"'
        },
    )
