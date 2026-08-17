"""Phase 14 M3 - Voice synthesis service."""

from pathlib import Path

from app.services.adapters.base import GenerationRequest


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
    ) -> list[str]:
        """逐句生成 TTS 音频，并返回落盘文件路径。"""
        character_voices = character_voices or {}
        output = Path(output_dir)
        output.mkdir(parents=True, exist_ok=True)
        voice_paths: list[str] = []

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
                voice_paths.append(result.urls[0])
        return voice_paths
