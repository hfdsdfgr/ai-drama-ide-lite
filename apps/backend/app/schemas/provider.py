"""Provider / Model API schemas。

响应永不包含 API Key，只提供 has_api_key 状态。
模型显示名 = model_id（不允许用户取名）。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModelType = Literal["llm", "image", "video"]


class ProviderCreate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    preset_key: str | None = None
    api_base_url: str = Field(default="", max_length=500)
    needs_key: bool = True
    api_key: str | None = Field(default=None, max_length=1000)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    api_base_url: str | None = Field(default=None, max_length=500)
    needs_key: bool | None = None
    enabled: bool | None = None
    api_key: str | None = Field(default=None, max_length=1000)


class ProviderOut(BaseModel):
    id: str
    name: str
    preset_key: str | None = None
    api_base_url: str = ""
    needs_key: bool = True
    enabled: bool = True
    has_api_key: bool = False
    model_count: int = 0
    created_at: datetime
    updated_at: datetime


class PresetOut(BaseModel):
    key: str
    name: str
    base_url: str
    needs_key: bool
    discoverable: bool = True


class ModelCreate(BaseModel):
    provider_id: str
    model_id: str = Field(min_length=1, max_length=200)
    model_type: ModelType = "llm"
    enabled: bool = True
    is_default_image: bool = False
    is_default_video: bool = False


class ModelUpdate(BaseModel):
    model_type: ModelType | None = None
    enabled: bool | None = None
    is_default_image: bool | None = None
    is_default_video: bool | None = None


class DefaultRequest(BaseModel):
    model_type: Literal["image", "video"] | None = None


class BulkModelsRequest(BaseModel):
    model_ids: list[str] = Field(min_length=1)


class BuiltinModelOut(BaseModel):
    id: str
    type: ModelType


class ModelOut(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_base_url: str = ""
    provider_needs_key: bool = True
    provider_has_api_key: bool = False
    model_id: str
    model_type: ModelType
    enabled: bool = True
    is_default_image: bool = False
    is_default_video: bool = False
    created_at: datetime
    updated_at: datetime
