"""Phase 15 — 项目生产阶段概览 Schema。"""

from typing import Literal

from pydantic import BaseModel, Field


StageStatus = Literal["pending", "active", "completed"]


class StageJobOut(BaseModel):
    job_id: str
    capability: str = ""
    status: str = ""
    progress: int = 0
    target_label: str = ""


class StageOut(BaseModel):
    key: str
    label: str
    status: StageStatus
    detail: str = ""
    jobs: list[StageJobOut] = Field(default_factory=list)


class ProjectOverviewOut(BaseModel):
    project_id: str
    stages: list[StageOut]


ProductionState = Literal[
    "missing",
    "ready",
    "stale",
    "active",
    "failed",
    "pending",
    "passed",
    "flagged",
    "not_started",
    "not_referenced",
]


class EpisodeAssetOut(BaseModel):
    asset_id: str
    asset_type: Literal["character", "location", "prop"]
    name: str
    has_image: bool = False


class EpisodeBlockerOut(BaseModel):
    code: str
    label: str
    target: Literal["assets", "storyboard"]


class EpisodeShotOut(BaseModel):
    shot_id: str
    scene_id: str
    scene_title: str = ""
    shot_number: int | None = None
    order_index: int = 0
    script_status: ProductionState
    asset_status: ProductionState
    prompt_status: ProductionState
    image_status: ProductionState
    video_status: ProductionState
    review_status: ProductionState
    image_dependency_state: Literal["none", "current", "stale", "pinned", "unknown", "broken"] = "none"
    video_dependency_state: Literal["none", "current", "stale", "pinned", "unknown", "broken"] = "none"
    dependency_issues: list["DependencyIssueOut"] = Field(default_factory=list)
    assets: list[EpisodeAssetOut] = Field(default_factory=list)
    blockers: list[EpisodeBlockerOut] = Field(default_factory=list)


class DependencyIssueOut(BaseModel):
    state: Literal["stale", "pinned", "unknown", "broken"]
    label: str
    media: Literal["image", "video"]
    source_id: str = ""
    source_name: str = ""
    used_version_id: str = ""
    used_version: int | None = None
    current_version_id: str = ""
    current_version: int | None = None


class EpisodeProductionOut(BaseModel):
    episode_id: str
    title: str = ""
    order_index: int = 0
    scene_count: int = 0
    shot_count: int = 0
    completed_shots: int = 0
    attention_count: int = 0
    active_count: int = 0
    stale_count: int = 0
    unknown_dependency_count: int = 0
    pinned_dependency_count: int = 0
    shots: list[EpisodeShotOut] = Field(default_factory=list)


class EpisodeWorkspaceOut(BaseModel):
    project_id: str
    episodes: list[EpisodeProductionOut] = Field(default_factory=list)


class EpisodePrepareOut(BaseModel):
    episode: EpisodeProductionOut
    message: str
    created_jobs: int = 0
    filled_prompts: int = 0
