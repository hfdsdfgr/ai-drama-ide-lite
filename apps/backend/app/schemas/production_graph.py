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
