"""Phase 13 M2 - Image Generation request schema."""

from typing import Literal

from pydantic import BaseModel, Field

from app.schemas.generation import GenerationJobOut


class ImageGenerateRequest(BaseModel):
    target_type: Literal["asset", "shot"]
    target_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    capability: str = Field(default="text_to_image", max_length=50)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    art_style: str | None = Field(default=None, max_length=50)
    negative_prompt: str = Field(default="", max_length=1000)
    reference_asset_ids: list[str] = Field(default_factory=list)
    # 精确引用历史版本；与旧的 asset id 字段互斥，避免隐式回退到 current。
    reference_version_ids: list[str] = Field(default_factory=list, max_length=16)
    pinned_version_ids: list[str] = Field(default_factory=list, max_length=16)
    prompt: str | None = Field(default=None, max_length=10000)
    regenerated_from_version_id: str | None = Field(default=None, max_length=100)


class BatchImageRequest(BaseModel):
    model_id: str = Field(min_length=1, max_length=100)
    shot_ids: list[str] = Field(min_length=1, max_length=100)
    batch_label: str = Field(default="批量关键帧", min_length=1, max_length=100)


class BatchImagePlanItemOut(BaseModel):
    shot_id: str
    label: str
    reason: str = ""


class BatchImagePlanOut(BaseModel):
    ready: list[BatchImagePlanItemOut] = Field(default_factory=list)
    skipped: list[BatchImagePlanItemOut] = Field(default_factory=list)


class BatchImageCreateOut(BatchImagePlanOut):
    batch_id: str
    jobs: list[GenerationJobOut] = Field(default_factory=list)
