"""Phase 14 M3 - Voice synthesis service."""

from dataclasses import dataclass, field
from pathlib import Path

from app.services.adapters.base import GenerationRequest, GenerationResult


@dataclass
class VoiceClip:
    """一条 TTS 输出：音频路径 + 台词归属 + 原始生成结果（含可选 alignment）。"""

    path: str
    character: str = ""
    text: str = ""
    result: GenerationResult | None = field(default=None)


class VoiceSynthesisService:
    def __init__(self, manager) -> None:
        self.manager = manager

    def synthesize(
        self,
        model_id: str,
        lines: list[dict],
        *,
        character_voices: dict[str, str] | None = None,
        voice_override: str = "",
        response_format: str = "",
        output_dir: str,
    ) -> list[VoiceClip]:
        """逐句生成 TTS 音频，返回结构化 VoiceClip（路径 + 归属 + 原始结果）。"""
        character_voices = character_voices or {}
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        voice_clips: list[VoiceClip] = []

        for line in lines:
            voice_id = voice_override or character_voices.get(
                line.get("character", ""), ""
            )
            result = self.manager.generate(
                model_id,
                "text_to_speech",
                GenerationRequest(
                    capability="text_to_speech",
                    prompt=line.get("text", ""),
                    model_id=model_id,
                    extra={
                        "voice": voice_id,
                        "response_format": response_format,
                        "output_dir": str(output),
                    },
                ),
            )
            if result.urls:
                voice_clips.append(
                    VoiceClip(
                        path=result.urls[0],
                        character=str(line.get("character", "")),
                        text=str(line.get("text", "")),
                        result=result,
                    )
                )
        return voice_clips
