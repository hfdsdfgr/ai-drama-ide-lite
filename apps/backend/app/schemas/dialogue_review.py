"""台词审核 Schema。"""

from pydantic import BaseModel, Field


class ReviewRunRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=100)
    model_id: str = Field(min_length=1, max_length=100)
    script_model_id: str = Field(min_length=1, max_length=100)


class ManualReviewRequest(BaseModel):
    shot_id: str = Field(min_length=1, max_length=100)
    consistent: bool
    detected_speech: str = Field(default="", max_length=5000)


class DecisionRequest(BaseModel):
    decision: str = Field(pattern="^(regenerate|delete_shot|keep)$")
