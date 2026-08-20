"""Phase 10 — 统一任务中心 Schema（/api/jobs）。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


JobStatusLiteral = Literal[
    "queued", "running", "paused", "completed", "failed", "cancelled"
]


class JobOut(BaseModel):
    job_id: str
    project_id: str | None = None
    type: str
    status: JobStatusLiteral
    progress: int = Field(default=0, ge=0, le=100)
    model_id: str = ""
    provider_id: str = ""
    capability: str = ""
    error: str | None = None
    error_category: str = ""
    attempts: int = 0
    result: dict | None = None
    created_at: datetime
    started_at: datetime | None = None
    completed_at: datetime | None = None
    paused_at: datetime | None = None
    cancelled_at: datetime | None = None


class BatchJobsRequest(BaseModel):
    project_id: str = Field(min_length=1, max_length=100)
    action: Literal["cancel", "pause", "resume"]
    stage: str | None = Field(default=None, max_length=50)


class BatchJobsResult(BaseModel):
    affected: int = 0
    jobs: list[JobOut] = Field(default_factory=list)
