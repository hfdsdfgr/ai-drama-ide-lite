"""Project prompt settings boundary: strict input, explicit restore semantics."""

from pydantic import BaseModel, ConfigDict, Field, StrictInt, StrictStr


class PromptPreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    rules: StrictStr | None = Field(max_length=12000)
    negative_prompt: StrictStr | None = Field(default=None, max_length=1000)


class PromptSettingsPut(PromptPreviewRequest):
    expected_revision: StrictInt = Field(ge=0)


class PromptStageOut(BaseModel):
    id: str
    label: str
    group: str
    description: str
    default_rules: str
    rules: str
    default_negative_prompt: str | None
    negative_prompt: str | None
    customized: bool
    allow_empty_rules: bool
    contract: str
    preview: str


class PromptSettingsOut(BaseModel):
    revision: int
    stages: list[PromptStageOut]


class PromptPreviewOut(BaseModel):
    stage_id: str
    id: str
    system_prompt: str
    preview: str
    rules: str
    negative_prompt: str | None
    contract: str
