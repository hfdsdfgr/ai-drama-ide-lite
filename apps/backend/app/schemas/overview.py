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
