"""Provider / Model API schemas。

响应永不包含 API Key，只提供 has_api_key 状态。
模型显示名 = model_id（不允许用户取名）。
"""

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field

ModelType = Literal["llm", "image", "video", "audio"]


class ProviderCreate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    preset_key: str | None = None
    protocol: str | None = None
    api_base_url: str = Field(default="", max_length=500)
    needs_key: bool = True
    api_key: str | None = Field(default=None, max_length=1000)


class ProviderUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    protocol: str | None = None
    api_base_url: str | None = Field(default=None, max_length=500)
    needs_key: bool | None = None
    enabled: bool | None = None
    api_key: str | None = Field(default=None, max_length=1000)


class ProviderOut(BaseModel):
    id: str
    name: str
    preset_key: str | None = None
    protocol: str = "openai_compat"
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
    protocol: str = "openai_compat"
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


class ModelCapabilityUpdate(BaseModel):
    """能力覆盖：source=manual 使用 capabilities；source=auto 重新按规则推断。"""

    capabilities: list[str] = Field(default_factory=list)
    source: Literal["auto", "manual"] = "manual"


class DefaultRequest(BaseModel):
    model_type: Literal["image", "video"] | None = None


class BulkModelsRequest(BaseModel):
    model_ids: list[str] = Field(min_length=1)


class BuiltinModelOut(BaseModel):
    id: str
    type: ModelType
    capabilities: list[str] = Field(default_factory=list)


class ModelOut(BaseModel):
    id: str
    provider_id: str
    provider_name: str
    provider_preset_key: str | None = None
    provider_protocol: str = "openai_compat"
    provider_enabled: bool = True
    provider_base_url: str = ""
    provider_needs_key: bool = True
    provider_has_api_key: bool = False
    model_id: str
    model_type: ModelType
    capabilities: list[str] = Field(default_factory=list)
    capability_source: Literal["auto", "manual"] = "auto"
    enabled: bool = True
    is_default_image: bool = False
    is_default_video: bool = False
    created_at: datetime
    updated_at: datetime


class ProviderCheckOut(BaseModel):
    label: str
    status: Literal["ok", "fail", "skipped"]
    detail: str = ""


class ModelCheckOut(BaseModel):
    model_id: str
    ok: bool
    detail: str = ""


class ProviderTestOut(BaseModel):
    provider_id: str
    ok: bool
    checks: list[ProviderCheckOut] = Field(default_factory=list)
    model_checks: list[ModelCheckOut] = Field(default_factory=list)
    tested_at: datetime
