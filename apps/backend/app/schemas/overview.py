"""Phase 15 — 项目生产阶段概览 Schema。"""

from typing import Literal

from pydantic import BaseModel


StageStatus = Literal["pending", "active", "completed"]


class StageOut(BaseModel):
    key: str
    label: str
    status: StageStatus
    detail: str = ""


class ProjectOverviewOut(BaseModel):
    project_id: str
    stages: list[StageOut]
