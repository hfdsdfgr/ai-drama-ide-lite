"""视觉一致性审核 Schema。"""

from pydantic import BaseModel, Field


class VisualReviewRunRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    review_type: str = Field(pattern="^(character|scene|continuity)$")


class ManualVisualReviewRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=100)
    review_type: str = Field(pattern="^(character|scene|continuity)$")
    consistent: bool
    issue: str = Field(default="", max_length=2000)


class VisualDecisionRequest(BaseModel):
    decision: str = Field(pattern="^(regenerate|delete_shot|keep)$")
