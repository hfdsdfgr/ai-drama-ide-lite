"""Phase 14 M1 — Shot Image → Video generation service."""

from app.core.errors import AppError
from app.services.asset_version_service import AssetVersionService
from app.services.generation_service import GenerationService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository


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
        with_audio: bool = False,
        reference_asset_ids: list[str] | None = None,
    ) -> dict:
        shot, _scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
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
        model = self.generation_service.manager.repo.get_model(model_id)
        capabilities = list(model.capabilities or [])
        supports_dialogue = "video_dialogue" in capabilities
        dialogue = (shot.dialogue or "").strip()
        if with_audio and supports_dialogue and dialogue and dialogue not in prompt:
            # 只有确认能生成原生对白/台词的模型才把台词写入提示词，
            # 仅支持原生音效的模型（如 CogVideoX）不写入，避免产出与剧情无关的音效。
            prompt = f"{prompt}\n\n对白：{dialogue}"
        return self.generation_service.create_job(
            model_id,
            "image_to_video",
            prompt,
            aspect_ratio=aspect_ratio or "720P",
            duration=duration,
            project_id=project_id,
            images=[image.file_path],
            reference_images=self._resolve_reference_image_paths(
                project_id, reference_asset_ids
            ),
            extra={
                "target_type": "shot",
                "target_id": shot_id,
                "with_audio": with_audio,
                # 未选择带音频（或模型只能带音效）时，落库前移除音轨，保证无声交付。
                "strip_audio": not with_audio,
                "source_refs": [
                    {
                        "type": "shot",
                        "id": shot_id,
                        "relation": "video_generated_from_shot",
                    }
                ],
            },
        )

    def _resolve_reference_image_paths(
        self, project_id: str, reference_asset_ids: list[str] | None
    ) -> list[str]:
        """Resolve selected reference assets to their current image versions.

        Assets without an image version are skipped (they do not block video
        generation); missing asset ids raise a clear error.
        """
        if not reference_asset_ids:
            return []
        assets = {
            asset["asset_id"]: asset
            for asset in StoryRepository(self.db_path).list_assets(project_id)
        }
        paths: list[str] = []
        for asset_id in reference_asset_ids:
            asset = assets.get(asset_id)
            if asset is None:
                raise AppError(
                    404,
                    "reference_asset_not_found",
                    f"reference asset not found: {asset_id}",
                )
            current = self.versions.get_current(
                project_id, asset["asset_type"], asset_id
            )
            if current is not None:
                paths.append(current.file_path)
        return paths

    def get_job(self, project_id: str, job_id: str) -> dict:
        record = self.generation_service.store.get(job_id)
        if record.project_id != project_id:
            raise AppError(404, "video_job_not_found", f"视频生成任务不存在: {job_id}")
        return self.generation_service.get_job(job_id)

    def get_current_version(self, project_id: str, shot_id: str):
        return self.versions.get_current(project_id, "shot_video", shot_id)
