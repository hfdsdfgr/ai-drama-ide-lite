"""Project-local workflow templates and per-episode production configuration."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class StoryboardConfig(StrictModel):
    enabled: bool = True
    model_id: str = Field(default="", max_length=100)
    capability: Literal["llm"] = "llm"


class ImageStageConfig(StrictModel):
    enabled: bool = True
    model_id: str = Field(default="", max_length=100)
    capability: Literal["text_to_image", "reference_image", "image_to_image"] = (
        "text_to_image"
    )
    aspect_ratio: str = Field(default="", max_length=20)


class VideoStageConfig(StrictModel):
    enabled: bool = False
    model_id: str = Field(default="", max_length=100)
    capability: Literal["image_to_video"] = "image_to_video"
    aspect_ratio: str = Field(default="", max_length=20)
    duration_mode: Literal["shot", "fixed"] = "shot"
    duration: Literal[5, 10, 15] = 5


class WorkflowConfig(StrictModel):
    auto_continue: bool = False
    storyboard: StoryboardConfig = Field(default_factory=StoryboardConfig)
    shot_images: ImageStageConfig = Field(default_factory=ImageStageConfig)
    videos: VideoStageConfig = Field(default_factory=VideoStageConfig)


class WorkflowTemplateCreate(StrictModel):
    name: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=300)
    config: WorkflowConfig


class WorkflowTemplateUpdate(StrictModel):
    expected_revision: int = Field(ge=1)
    name: str | None = Field(default=None, min_length=1, max_length=80)
    description: str | None = Field(default=None, max_length=300)
    config: WorkflowConfig | None = None


class WorkflowTemplateOut(StrictModel):
    id: str
    project_id: str
    name: str
    description: str
    schema_version: int
    revision: int
    config: WorkflowConfig
    created_at: str
    updated_at: str


class EpisodeWorkflowConfigOut(StrictModel):
    project_id: str
    episode_id: str
    revision: int
    config: WorkflowConfig
    updated_at: str | None = None


class EpisodeWorkflowConfigPut(StrictModel):
    expected_revision: int = Field(ge=0)
    config: WorkflowConfig


class TemplatePreviewRequest(StrictModel):
    template_id: str = Field(min_length=1, max_length=100)


class TemplateDiffItem(StrictModel):
    field_path: str
    label: str
    current_value: str | int | bool
    template_value: str | int | bool
    compatible: bool = True
    reason: str = ""
    candidates: list[dict] = Field(default_factory=list)


class TemplatePreviewOut(StrictModel):
    template_id: str
    template_revision: int
    config_revision: int
    differences: list[TemplateDiffItem]


class TemplateApplyRequest(StrictModel):
    template_id: str = Field(min_length=1, max_length=100)
    template_revision: int = Field(ge=1)
    config_revision: int = Field(ge=0)
    selected_fields: list[str] = Field(min_length=1, max_length=20)
