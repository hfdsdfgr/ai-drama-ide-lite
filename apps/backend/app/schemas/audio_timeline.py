"""Voice / Timeline / Lip Sync schemas（Phase 14 M3）。

三个概念严格分离：
1. Voice Generation：只生成音频 + 真实 alignment 数据。
2. Timeline / Alignment：把音频、台词、Shot 映射到真实时间轴。
3. Lip Sync：只消费视频 + 音频，独立 Job。
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator


AlignmentSource = Literal["provider", "forced_alignment", "audio_duration_only"]


class AlignmentChar(BaseModel):
    """字符级时间戳（TTS Provider / Forced Alignment 提供）。"""

    char: str = ""
    start_time: float = 0
    end_time: float = 0


class AlignmentWord(BaseModel):
    """词级时间戳（Forced Alignment 提供）。"""

    word: str = ""
    start_time: float = 0
    end_time: float = 0


class AlignmentPhoneme(BaseModel):
    """音素级时间戳（预留，第一阶段不实现）。"""

    phoneme: str = ""
    start_time: float = 0
    end_time: float = 0


class AlignmentResult(BaseModel):
    """真实时间轴来源与数据。

    source 优先级：
    provider -> TTS Provider 返回真实 timestamps / alignment；
    forced_alignment -> 对最终音频执行 Forced Alignment；
    audio_duration_only -> 两者都不可用，只记录真实 duration，不伪造字符级时间戳。
    """

    source: AlignmentSource
    duration: float | None = None
    characters: list[AlignmentChar] = Field(default_factory=list)
    words: list[AlignmentWord] = Field(default_factory=list)
    phonemes: list[AlignmentPhoneme] = Field(default_factory=list)
    confidence: float | None = None
    raw: dict = Field(default_factory=dict)


class DialogueClipSegment(BaseModel):
    """一句台词在某个 Shot 内的片段，支持一句台词跨多个 Shot。"""

    shot_id: str
    start_time: float = 0
    end_time: float = 0

    @model_validator(mode="after")
    def _validate_times(self):
        if self.start_time < 0 or self.end_time < self.start_time:
            raise ValueError(
                f"segment {self.shot_id}: invalid time range "
                f"[{self.start_time}, {self.end_time}]"
            )
        return self


class DialogueClip(BaseModel):
    """一条独立台词 clip。

    字段对应产品要求：
    - start_time / end_time：整句台词的起止（真实时间轴）；
    - audio_asset_id：TTS 生成的音频资产；
    - alignment：字符 / 词级 alignment 数据（phoneme 预留）；
    - speaker_id / voice_profile_id：角色与音色；
    - shot_id：主 Shot（兼容单 Shot 场景）；
    - segments：跨 Shot 片段（一句台词可覆盖多个 Shot）；
    - version：版本号。
    """

    id: str
    project_id: str
    start_time: float = 0
    end_time: float = 0
    audio_asset_id: str = ""
    alignment: AlignmentResult | None = None
    speaker_id: str = ""
    voice_profile_id: str = ""
    shot_id: str = ""
    version: int = 1
    segments: list[DialogueClipSegment] = Field(default_factory=list)
    created_at: str = ""
    updated_at: str = ""

    @model_validator(mode="after")
    def _validate_times(self):
        if self.start_time < 0 or self.end_time < self.start_time:
            raise ValueError(
                f"invalid clip time range [{self.start_time}, {self.end_time}]"
            )
        if self.version < 1:
            raise ValueError("version must be >= 1")
        return self

    def total_duration(self) -> float:
        """整句台词的真实时长。"""
        return max(0.0, self.end_time - self.start_time)
