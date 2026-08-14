"""Phase 9 — 资产版本 Schema。"""

from datetime import datetime

from pydantic import BaseModel, Field


class AssetVersionOut(BaseModel):
    id: str
    entity_type: str
    entity_id: str
    version: int
    model_id: str = ""
    provider_id: str = ""
    job_id: str = ""
    payload: dict = Field(default_factory=dict)
    is_current: bool
    created_at: datetime
    file_url: str
