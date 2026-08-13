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


class BibleLocation(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)


class BibleProp(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = Field(default="", max_length=2000)


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


class AiChapterOut(BaseModel):
    title: str
    content: str
    summary: str = ""
