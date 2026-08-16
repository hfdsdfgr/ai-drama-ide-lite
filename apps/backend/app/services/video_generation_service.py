"""Phase 14 M1 — Shot Image → Video generation service."""

from app.core.errors import AppError
from app.services.asset_version_service import AssetVersionService
from app.services.generation_service import GenerationService
from app.services.script_repo import ScriptRepository


class VideoGenerationService:
    def __init__(
        self,
        generation_service: GenerationService,
        db_path,
        asset_version_service: AssetVersionService,
    ) -> None:
        self.generation_service = generation_service
        self.db_path = db_path
        self.versions = asset_version_service

    def start_shot_video(
        self,
        project_id: str,
        shot_id: str,
        model_id: str,
        prompt: str,
        *,
        duration: int = 5,
        aspect_ratio: str | None = None,
    ) -> dict:
        ScriptRepository(self.db_path).get_shot_with_scene(project_id, shot_id)
        image = self.versions.get_current(project_id, "shot", shot_id)
        if image is None:
            raise AppError(
                422,
                "shot_image_missing",
                "请先生成该镜头的分镜图片，再生成视频",
            )
        prompt = prompt.strip()
        if not prompt:
            raise AppError(422, "prompt_required", "请输入视频生成提示词")
        return self.generation_service.create_job(
            model_id,
            "image_to_video",
            prompt,
            aspect_ratio=aspect_ratio or "720P",
            duration=duration,
            project_id=project_id,
            images=[image.file_path],
            extra={
                "target_type": "shot",
                "target_id": shot_id,
                "source_refs": [
                    {
                        "type": "shot",
                        "id": shot_id,
                        "relation": "video_generated_from_shot",
                    }
                ],
            },
        )

    def get_job(self, project_id: str, job_id: str) -> dict:
        record = self.generation_service.store.get(job_id)
        if record.project_id != project_id:
            raise AppError(404, "video_job_not_found", f"视频生成任务不存在: {job_id}")
        return self.generation_service.get_job(job_id)

    def get_current_version(self, project_id: str, shot_id: str):
        return self.versions.get_current(project_id, "shot_video", shot_id)
