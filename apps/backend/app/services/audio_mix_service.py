"""Phase 14 M3 - Audio mixing service."""

from app.services.media_mix import mix_audio_to_master


class AudioMixService:
    def mix_to_master(
        self,
        video_path: str,
        voice_paths: list[str],
        output_path: str,
        bgm_path: str | None = None,
    ) -> str:
        return mix_audio_to_master(
            video_path,
            voice_paths,
            output_path,
            bgm_path=bgm_path,
        )
