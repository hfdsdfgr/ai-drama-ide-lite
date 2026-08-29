"""剧情一致性审核 Schema。"""

from pydantic import BaseModel, Field


class StoryReviewRunRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)


class ManualStoryReviewRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=100)
    consistent: bool
    issue: str = Field(default="", max_length=2000)


class StoryDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(regenerate|delete_shot|keep)$")
