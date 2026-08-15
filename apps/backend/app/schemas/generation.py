"""Generation Job schemas（Phase 5）。"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class GenerationJobCreate(BaseModel):
    model_id: str
    capability: str
    prompt: str = Field(min_length=1, max_length=2000)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    duration: int | None = Field(default=None, ge=2, le=15)
    images: list[str] = Field(default_factory=list, max_length=10)
    negative_prompt: str = Field(default="", max_length=1000)


class GenerationResultOut(BaseModel):
    urls: list[str] = Field(default_factory=list)
    meta: dict = Field(default_factory=dict)


class GenerationJobOut(BaseModel):
    job_id: str
    model_id: str
    capability: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    error: str | None = None
    result: GenerationResultOut | None = None
    created_at: datetime
