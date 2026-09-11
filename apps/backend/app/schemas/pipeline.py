"""一键生产编排 Schema。"""

from pydantic import BaseModel

from app.schemas.workflow_template import WorkflowConfig


class PipelineStartRequest(BaseModel):
    auto_continue: bool = False
    include_videos: bool = False
    quality_review: bool = False


class EpisodePipelineStartRequest(BaseModel):
    expected_config_revision: int = 0


class EpisodePipelinePlanOut(BaseModel):
    project_id: str
    episode_id: str
    episode_title: str
    config_revision: int
    config: WorkflowConfig
    stages: list[dict]
    can_start: bool
