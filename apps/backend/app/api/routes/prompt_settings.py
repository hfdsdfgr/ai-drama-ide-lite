"""Offline project prompt configuration; saving and previewing never invoke AI."""

from fastapi import APIRouter, Request

from app.schemas.prompt_settings import (
    PromptPreviewOut,
    PromptPreviewRequest,
    PromptSettingsOut,
    PromptSettingsPut,
)

router = APIRouter(prefix="/api/projects/{project_id}/prompt-settings", tags=["prompt-settings"])


@router.get("", response_model=PromptSettingsOut)
def list_settings(project_id: str, request: Request):
    return request.app.state.prompt_settings_service.list_settings(project_id)


@router.put("/{stage_id}", response_model=PromptSettingsOut)
def update_settings(project_id: str, stage_id: str, payload: PromptSettingsPut, request: Request):
    return request.app.state.prompt_settings_service.update(
        project_id, stage_id, **payload.model_dump(exclude_unset=True)
    )


@router.post("/{stage_id}/preview", response_model=PromptPreviewOut)
def preview_settings(project_id: str, stage_id: str, payload: PromptPreviewRequest, request: Request):
    return request.app.state.prompt_settings_service.preview(
        project_id, stage_id, **payload.model_dump(exclude_unset=True)
    )
