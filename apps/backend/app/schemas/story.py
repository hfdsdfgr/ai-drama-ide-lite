"""Story Bible / 章节抽取 schemas（Phase 6 — LLM Story Engine）。

这些模型同时用于：LLM 输出解析校验（Pydantic）、API 响应。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class ExtractedCharacter(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=1000)
    role_hint: str = Field(default="", max_length=50)


class ExtractedLocation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class ExtractedProp(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=1000)


class ExtractedEvent(BaseModel):
    summary: str = Field(min_length=1, max_length=1000)
    importance: Literal["low", "medium", "high"] = "medium"
    characters: list[str] = Field(default_factory=list)


class ChapterExtraction(BaseModel):
    chapter_summary: str = Field(default="", max_length=1000)
    characters: list[ExtractedCharacter] = Field(default_factory=list)
    locations: list[ExtractedLocation] = Field(default_factory=list)
    props: list[ExtractedProp] = Field(default_factory=list)
    events: list[ExtractedEvent] = Field(default_factory=list)


class BibleCharacter(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    aliases: list[str] = Field(default_factory=list)
    summary: str = Field(default="", max_length=2000)
    role_hint: str = Field(default="", max_length=50)
    # Phase 8 视觉资产卡：固定人设描述，后续生图/生视频必须复用 reference_prompt
    identity: str = Field(default="", max_length=500)  # 身份标签：身份/年龄/阵营
    appearance: str = Field(default="", max_length=1000)  # 面部特征：脸型/五官/瞳色/肤色
    hairstyle: str = Field(default="", max_length=300)  # 发型发色
    costume: str = Field(default="", max_length=1000)  # 服装配饰
    build: str = Field(default="", max_length=300)  # 体型姿态
    marks: str = Field(default="", max_length=300)  # 特殊标记：泪痣/耳钉/疤痕/纹身
    personality: str = Field(default="", max_length=500)  # 性格标签
    style: str = Field(default="", max_length=300)  # 风格参考：写实/动漫/国风/赛博
    reference_prompt: str = Field(default="", max_length=4000)
    asset_id: str = Field(default="", max_length=100)


class BibleLocation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    # Phase 8 视觉资产卡
    environment: str = Field(default="", max_length=1000)  # 环境描述
    time: str = Field(default="", max_length=200)  # 时间段
    lighting: str = Field(default="", max_length=500)  # 光线
    style: str = Field(default="", max_length=300)  # 视觉风格
    reference_prompt: str = Field(default="", max_length=4000)
    asset_id: str = Field(default="", max_length=100)


class BibleProp(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)
    # Phase 8 视觉资产卡
    material: str = Field(default="", max_length=500)  # 材质
    reference: str = Field(default="", max_length=1000)  # 参考/用途
    reference_prompt: str = Field(default="", max_length=4000)
    asset_id: str = Field(default="", max_length=100)


class AssetCardOut(BaseModel):
    """资产卡输出：Bible 实体 + 固定图片规格（同类型资产图片格式固定）。"""

    asset_type: str
    asset_id: str
    name: str
    image_spec: dict
    reference_prompt: str = ""
    fields: dict


class AssetUpdateRequest(BaseModel):
    asset_type: str
    name: str = Field(min_length=1, max_length=100)
    patch: dict


class AssetDeleteRequest(BaseModel):
    asset_type: str
    name: str = Field(min_length=1, max_length=100)


class AssetGenerateRequest(BaseModel):
    model_id: str


class AssetGenerateJobOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float | None = None
    detail: str = ""
    error: str | None = None
    created_at: datetime


class AssetGenerateResult(BaseModel):
    """LLM 补全输出：按 name 匹配 Bible 实体，缺字段不覆盖。"""

    characters: list[BibleCharacter] = Field(default_factory=list)
    locations: list[BibleLocation] = Field(default_factory=list)
    props: list[BibleProp] = Field(default_factory=list)


class BibleEvent(BaseModel):
    summary: str = Field(min_length=1, max_length=2000)
    importance: str = "medium"
    characters: list[str] = Field(default_factory=list)
    chapter_index: int = 0


class StoryBible(BaseModel):
    synopsis: str = Field(default="", max_length=5000)
    characters: list[BibleCharacter] = Field(default_factory=list)
    locations: list[BibleLocation] = Field(default_factory=list)
    props: list[BibleProp] = Field(default_factory=list)
    events: list[BibleEvent] = Field(default_factory=list)
    conflicts: list[str] = Field(default_factory=list)
    plotlines: list[str] = Field(default_factory=list)
    foreshadowing: list[str] = Field(default_factory=list)


class AnalysisRequest(BaseModel):
    novel_id: str
    model_id: str
    mode: Literal["full", "merge"] = "full"


class AnalysisJobOut(BaseModel):
    job_id: str
    status: Literal["queued", "running", "completed", "failed", "cancelled"]
    progress: float | None = None
    detail: str = ""
    error: str | None = None
    created_at: datetime


class StoryBibleOut(BaseModel):
    bible: StoryBible | None = None


# ---------- AI 撰写向导 ----------


class AiNovelBrief(BaseModel):
    genre: str = Field(default="", max_length=50)
    audience: str = Field(default="", max_length=50)
    ideas: str = Field(default="", max_length=3000)
    complexity: int = Field(default=5, ge=1, le=10)
    chapter_count: int = Field(default=10, ge=1, le=60)


class OutlineChapter(BaseModel):
    title: str = Field(min_length=1, max_length=100)
    summary: str = Field(default="", max_length=1000)


class AiOutlineResult(BaseModel):
    title: str = Field(default="", max_length=100)
    chapters: list[OutlineChapter] = Field(default_factory=list)


class AiOutlineRequest(BaseModel):
    model_id: str
    brief: AiNovelBrief


class AiChapterRequest(BaseModel):
    model_id: str
    brief: AiNovelBrief
    outline: list[OutlineChapter] = Field(min_length=1, max_length=60)
    chapter_index: int = Field(ge=0)
    user_instruction: str = Field(default="", max_length=2000)
    previous_summaries: list[str] = Field(default_factory=list, max_length=100)


class AiContinueRequest(BaseModel):
    model_id: str
    brief: AiNovelBrief
    user_instruction: str = Field(default="", max_length=2000)
    context_chapter_count: int = Field(default=3, ge=1, le=10)


class AiChapterOut(BaseModel):
    title: str
    content: str
    summary: str = ""
