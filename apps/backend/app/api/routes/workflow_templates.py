"""Project-local workflow template and per-episode configuration endpoints."""

from fastapi import APIRouter, Request, Response

from app.schemas.workflow_template import (
    EpisodeWorkflowConfigOut,
    EpisodeWorkflowConfigPut,
    TemplateApplyRequest,
    TemplatePreviewOut,
    TemplatePreviewRequest,
    WorkflowTemplateCreate,
    WorkflowTemplateOut,
    WorkflowTemplateUpdate,
)


router = APIRouter(prefix="/api/projects/{project_id}", tags=["workflow-templates"])


def _service(request: Request):
    return request.app.state.workflow_template_service


@router.get("/workflow-templates", response_model=list[WorkflowTemplateOut])
def list_templates(project_id: str, request: Request):
    return _service(request).list_templates(project_id)


@router.post("/workflow-templates", response_model=WorkflowTemplateOut, status_code=201)
def create_template(project_id: str, payload: WorkflowTemplateCreate, request: Request):
    return _service(request).create_template(project_id, payload.name, payload.description, payload.config)


@router.get("/workflow-templates/{template_id}", response_model=WorkflowTemplateOut)
def get_template(project_id: str, template_id: str, request: Request):
    return _service(request).get_template(project_id, template_id)


@router.patch("/workflow-templates/{template_id}", response_model=WorkflowTemplateOut)
def update_template(project_id: str, template_id: str, payload: WorkflowTemplateUpdate, request: Request):
    return _service(request).update_template(project_id, template_id, **payload.model_dump())


@router.delete("/workflow-templates/{template_id}", status_code=204)
def delete_template(project_id: str, template_id: str, request: Request):
    _service(request).delete_template(project_id, template_id)
    return Response(status_code=204)


@router.get("/episodes/{episode_id}/workflow-config", response_model=EpisodeWorkflowConfigOut)
def get_episode_config(project_id: str, episode_id: str, request: Request):
    return _service(request).get_episode_config(project_id, episode_id)


@router.put("/episodes/{episode_id}/workflow-config", response_model=EpisodeWorkflowConfigOut)
def put_episode_config(project_id: str, episode_id: str, payload: EpisodeWorkflowConfigPut, request: Request):
    return _service(request).put_episode_config(project_id, episode_id, payload.expected_revision, payload.config)


@router.post("/episodes/{episode_id}/workflow-config/preview-template", response_model=TemplatePreviewOut)
def preview_template(project_id: str, episode_id: str, payload: TemplatePreviewRequest, request: Request):
    return _service(request).preview(project_id, episode_id, payload.template_id)


@router.post("/episodes/{episode_id}/workflow-config/apply-template", response_model=EpisodeWorkflowConfigOut)
def apply_template(project_id: str, episode_id: str, payload: TemplateApplyRequest, request: Request):
    return _service(request).apply(project_id, episode_id, **payload.model_dump())
