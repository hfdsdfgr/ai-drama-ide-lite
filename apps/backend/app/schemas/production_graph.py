"""Phase 11 — 生产依赖图 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class ProductionEdgeCreate(BaseModel):
    upstream_type: str
    upstream_id: str
    upstream_version: int | None = None
    downstream_type: str
    downstream_id: str
    relation: str = ""


class ProductionEdgeOut(BaseModel):
    id: str
    upstream_type: str
    upstream_id: str
    upstream_version: int | None = None
    downstream_type: str
    downstream_id: str
    relation: str = ""
    created_at: datetime


class AffectedNodeOut(BaseModel):
    type: str
    id: str
    relation: str = ""


class AffectedNodesOut(BaseModel):
    changed_node: dict = Field(default_factory=dict)
    affected: list[AffectedNodeOut] = Field(default_factory=list)


class RegenerationPlanItemOut(BaseModel):
    shot_id: str
    label: str
    reason: str = ""
    dependency_state: str = "unknown"


class RegenerationPlanOut(BaseModel):
    changed_node: dict = Field(default_factory=dict)
    image_shots: list[RegenerationPlanItemOut] = Field(default_factory=list)
    video_shots: list[RegenerationPlanItemOut] = Field(default_factory=list)


class DependencyViewNodeOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    label: str
    version: int | None = None
    current_version: int | None = None
    state: str = "unknown"
    target: dict = Field(default_factory=dict)


class DependencyViewEdgeOut(BaseModel):
    source: str
    target: str
    relation: str = ""


class ShotDependencyViewOut(BaseModel):
    shot_id: str
    label: str
    nodes: list[DependencyViewNodeOut] = Field(default_factory=list)
    edges: list[DependencyViewEdgeOut] = Field(default_factory=list)
    issues: list[dict] = Field(default_factory=list)


class DependencyViewOut(BaseModel):
    project_id: str
    scope: dict = Field(default_factory=dict)
    shots: list[ShotDependencyViewOut] = Field(default_factory=list)
    total: int = 0
