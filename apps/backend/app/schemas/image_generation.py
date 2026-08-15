"""Phase 13 M2 - Image Generation request schema."""

from typing import Literal

from pydantic import BaseModel, Field


class ImageGenerateRequest(BaseModel):
    target_type: Literal["asset", "shot"]
    target_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    capability: str = Field(default="text_to_image", max_length=50)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    art_style: str | None = Field(default=None, max_length=50)
    negative_prompt: str = Field(default="", max_length=1000)
    reference_asset_ids: list[str] = Field(default_factory=list, max_length=3)
