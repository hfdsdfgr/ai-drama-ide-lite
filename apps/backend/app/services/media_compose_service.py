"""Phase 14 M3 - Media compose service."""

from app.services.media_mix import compose_video_with_audio


class MediaComposeService:
    def compose(
        self,
        video_path: str,
        audio_path: str,
        output_path: str,
    ) -> str:
        return compose_video_with_audio(video_path, audio_path, output_path)
