"""Phase 14 M1 - Video generation request schema."""

from pydantic import BaseModel, Field


class VideoGenerateRequest(BaseModel):
    target_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    prompt: str = Field(min_length=1, max_length=2000)
    duration: int = Field(default=5, ge=2, le=15)
    aspect_ratio: str | None = Field(default=None, max_length=20)
    with_audio: bool = False
    reference_asset_ids: list[str] = Field(default_factory=list)


class VideoComposeRequest(BaseModel):
    scene_id: str = Field(default="", max_length=100)
    episode_id: str = Field(default="", max_length=100)


class AudioDubRequest(BaseModel):
    voice_model_id: str = Field(default="", max_length=100)
    script_model_id: str = Field(default="", max_length=100)
    voice: str = Field(default="", max_length=200)
    bgm_path: str = Field(default="", max_length=500)
