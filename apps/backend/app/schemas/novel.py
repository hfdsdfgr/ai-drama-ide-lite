"""Novel / Chapter API schemas."""

from datetime import datetime

from pydantic import BaseModel, Field


class NovelCreate(BaseModel):
    title: str = Field(min_length=1, max_length=300)


class NovelUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=300)
    ai_brief: str | None = Field(default=None, max_length=5000)


class Novel(BaseModel):
    id: str
    project_id: str
    title: str
    source_type: str = "original"
    ai_brief: str = ""
    chapter_count: int = 0
    created_at: datetime
    updated_at: datetime


class ChapterCreate(BaseModel):
    title: str = Field(default="", max_length=300)
    content: str | None = Field(default=None)


class ChapterUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    content: str | None = Field(default=None)


class Chapter(BaseModel):
    id: str
    novel_id: str
    title: str = ""
    content: str = ""
    order_index: int = 0
    created_at: datetime
    updated_at: datetime


class NovelDetail(BaseModel):
    novel: Novel
    chapters: list[Chapter]


class NovelAiRequest(BaseModel):
    model_id: str
    chapter_id: str


class NovelAiResult(BaseModel):
    text: str
