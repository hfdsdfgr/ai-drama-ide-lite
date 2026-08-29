"""一键生产编排 Schema。"""

from pydantic import BaseModel


class PipelineStartRequest(BaseModel):
    auto_continue: bool = False
    include_videos: bool = False
    quality_review: bool = False
