"""剧本引擎 schemas：Episode / Scene / Shot（Phase 7）。"""

from datetime import datetime

from pydantic import BaseModel, Field


class Episode(BaseModel):
    id: str
    project_id: str
    novel_id: str | None = None
    title: str = ""
    summary: str = ""
    order_index: int = 0
    source_chapter_index: int | None = None
    created_at: datetime
    updated_at: datetime


class EpisodeCreate(BaseModel):
    title: str = Field(default="", max_length=200)
    summary: str = Field(default="", max_length=3000)
    order_index: int = Field(default=0, ge=0)
    source_chapter_index: int | None = Field(default=None, ge=0)


class Scene(BaseModel):
    id: str
    project_id: str
    episode_id: str | None = None
    novel_id: str | None = None
    title: str = ""
    order_index: int = 0
    slugline: str = ""
    action: str = ""
    dialogue: str = ""
    created_at: datetime
    updated_at: datetime


class SceneCreate(BaseModel):
    episode_id: str | None = None
    title: str = Field(default="", max_length=200)
    order_index: int = Field(default=0, ge=0)
    slugline: str = Field(default="", max_length=300)
    action: str = Field(default="", max_length=6000)
    dialogue: str = Field(default="", max_length=10000)


class Shot(BaseModel):
    id: str
    project_id: str
    scene_id: str | None = None
    shot_number: int | None = None
    order_index: int = 0
    shot_type: str = ""
    camera: str = ""
    characters: str = ""
    action: str = ""
    lighting: str = ""
    dialogue: str = ""
    duration: float = 0
    prompt: str = ""
    created_at: datetime
    updated_at: datetime


class ShotCreate(BaseModel):
    scene_id: str | None = None
    shot_number: int | None = Field(default=None, ge=1)
    order_index: int = Field(default=0, ge=0)
    shot_type: str = Field(default="", max_length=50)
    camera: str = Field(default="", max_length=300)
    characters: str = Field(default="", max_length=500)
    action: str = Field(default="", max_length=3000)
    lighting: str = Field(default="", max_length=300)
    dialogue: str = Field(default="", max_length=2000)
    duration: float = Field(default=0, ge=0, le=600)
    prompt: str = Field(default="", max_length=3000)


class EpisodeDetail(BaseModel):
    episode: Episode
    scenes: list[Scene] = Field(default_factory=list)


class SceneDetail(BaseModel):
    scene: Scene
    shots: list[Shot] = Field(default_factory=list)


# ---------- AI 生成 ----------


class AiEpisodePlan(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    summary: str = Field(default="", max_length=3000)


class AiSceneScript(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    slugline: str = Field(default="", max_length=300)
    action: str = Field(default="", max_length=6000)
    dialogue: str = Field(default="", max_length=10000)


class AiEpisodeScriptResult(BaseModel):
    episode: AiEpisodePlan
    scenes: list[AiSceneScript] = Field(default_factory=list, max_length=20)


class AiShotOut(BaseModel):
    shot_type: str = Field(default="", max_length=50)
    camera: str = Field(default="", max_length=300)
    characters: str = Field(default="", max_length=500)
    action: str = Field(default="", max_length=3000)
    lighting: str = Field(default="", max_length=300)
    dialogue: str = Field(default="", max_length=2000)
    duration: float = Field(default=3, ge=0.5, le=120)
    prompt: str = Field(default="", max_length=3000)


class AiShotsResult(BaseModel):
    shots: list[AiShotOut] = Field(default_factory=list, min_length=1, max_length=30)


class ScriptGenerateRequest(BaseModel):
    novel_id: str
    model_id: str
    chapter_index: int | None = Field(default=None, ge=0)
    user_instruction: str = Field(default="", max_length=2000)


class ShotsGenerateRequest(BaseModel):
    model_id: str
    scene_id: str
    user_instruction: str = Field(default="", max_length=2000)
