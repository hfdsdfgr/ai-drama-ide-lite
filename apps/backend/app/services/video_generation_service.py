"""Phase 14 M1 — Shot Image → Video generation service."""

from pathlib import Path

from app.core.errors import AppError
from app.services.asset_version_service import AssetVersionService
from app.services.reference_media import ReferenceMediaRepository
from app.services.generation_service import GenerationService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository


VIDEO_MOTION_CONSISTENCY = (
    "\n\n动作自然连贯，符合真实重力与物理规律；"
    "角色外观、发型、服装、场景与首帧画面及参考图保持一致，画风统一；"
    "画面中不要出现文字、字幕、水印。"
)


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
        with_audio: bool | None = None,
        reference_asset_ids: list[str] | None = None,
        reference_version_ids: list[str] | None = None,
        pinned_version_ids: list[str] | None = None,
        source_image_version_id: str | None = None,
        regenerated_from_version_id: str | None = None,
    ) -> dict:
        shot, _scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
        reference_asset_ids = reference_asset_ids or []
        reference_version_ids = reference_version_ids or []
        pinned = set(pinned_version_ids or [])
        if not pinned.issubset([*reference_version_ids, source_image_version_id]):
            raise AppError(422, "invalid_pinned_reference", "固定版本必须是本次选择的参考版本")
        if regenerated_from_version_id:
            original = self.versions.get(regenerated_from_version_id)
            if (original.project_id, original.entity_type, original.entity_id) != (project_id, "shot_video", shot_id):
                raise AppError(422, "invalid_regeneration_source", "重新生成的来源版本不属于当前镜头")
        if reference_asset_ids and reference_version_ids:
            raise AppError(422, "ambiguous_reference_input", "参考资产与参考版本不能同时提交")
        image = (
            self.versions.get(source_image_version_id)
            if source_image_version_id
            else self.versions.get_current(project_id, "shot", shot_id)
        )
        if source_image_version_id and image and (
            image.project_id != project_id
            or image.entity_type != "shot"
            or image.entity_id != shot_id
        ):
            raise AppError(422, "invalid_source_image_version", "源关键帧版本不属于当前镜头")
        if image is None:
            raise AppError(
                422,
                "shot_image_missing",
                "请先生成该镜头的分镜图片，再生成视频",
            )
        if source_image_version_id and not Path(image.file_path).is_file():
            raise AppError(422, "source_image_missing", "源关键帧版本文件不存在")
        prompt = prompt.strip()
        if not prompt:
            raise AppError(422, "prompt_required", "请输入视频生成提示词")
        # 图生视频首帧已锁定画面，文字补充运动与一致性约束，避免角色/画风漂移。
        user_prompt = prompt
        prompt = user_prompt + VIDEO_MOTION_CONSISTENCY
        model = self.generation_service.manager.repo.get_model(model_id)
        capabilities = list(model.capabilities or [])
        supports_dialogue = "video_dialogue" in capabilities
        if with_audio is None:
            # 未显式指定时跟随模型能力：能带原生对白/音效的模型默认带声音，
            # 避免调用方忘记传参时产出无声视频。
            with_audio = supports_dialogue or "video_audio" in capabilities
        dialogue = (shot.dialogue or "").strip()
        if with_audio and supports_dialogue and dialogue and dialogue not in prompt:
            # 只有确认能生成原生对白/台词的模型才把台词写入提示词，
            # 仅支持原生音效的模型（如 CogVideoX）不写入，避免产出与剧情无关的音效。
            prompt = f"{prompt}\n\n对白：{dialogue}"
        reference_images, reference_refs = self._resolve_reference_image_paths(
            project_id, reference_asset_ids, reference_version_ids
        )
        for ref in reference_refs:
            ref["selection_mode"] = "historical" if ref["version_id"] in pinned else "current"
        return self.generation_service.create_job(
            model_id,
            "image_to_video",
            prompt,
            aspect_ratio=aspect_ratio or "720P",
            duration=duration,
            project_id=project_id,
            images=[image.file_path],
            reference_images=reference_images,
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
                        "version_id": getattr(image, "id", ""),
                        "version": getattr(image, "version", None),
                        "entity_type": "shot",
                        "selection_mode": "historical" if getattr(image, "id", "") in pinned else "current",
                    }
                ] + reference_refs,
                "user_prompt": user_prompt,
                "regenerated_from_version_id": regenerated_from_version_id or "",
            },
        )

    def _resolve_reference_image_paths(
        self,
        project_id: str,
        reference_asset_ids: list[str] | None,
        reference_version_ids: list[str] | None,
    ) -> tuple[list[str], list[dict]]:
        """Resolve selected reference assets to their current image versions.

        Assets without an image version are skipped (they do not block video
        generation); missing asset ids raise a clear error.
        """
        if reference_version_ids:
            paths: list[str] = []
            refs: list[dict] = []
            seen: set[str] = set()
            for version_id in reference_version_ids:
                if version_id in seen:
                    continue
                seen.add(version_id)
                record = self.versions.get(version_id)
                if record.project_id != project_id or record.entity_type not in {"character", "location", "prop", "reference_image"}:
                    raise AppError(422, "invalid_reference_version", "参考图片版本不属于当前项目或类型不支持")
                if not record.file_path or not Path(record.file_path).is_file():
                    raise AppError(422, "reference_image_missing", "参考图片版本文件不存在")
                paths.append(record.file_path)
                refs.append({
                    "type": "asset",
                    "id": record.entity_id,
                    "entity_type": record.entity_type,
                    "version_id": record.id,
                    "version": record.version,
                    "relation": "shot_references_asset",
                })
            return paths, refs
        if not reference_asset_ids:
            return [], []
        assets = {
            asset["asset_id"]: asset
            for asset in StoryRepository(self.db_path).list_assets(project_id)
        }
        assets.update(
            {
                item["id"]: {
                    "asset_id": item["id"],
                    "asset_type": "reference_image",
                    "name": item["name"],
                }
                for item in ReferenceMediaRepository(self.db_path).list(project_id)
            }
        )
        paths: list[str] = []
        refs: list[dict] = []
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
                refs.append({
                    "type": "asset",
                    "id": asset_id,
                    "entity_type": asset["asset_type"],
                    "version_id": getattr(current, "id", ""),
                    "version": getattr(current, "version", None),
                    "relation": "shot_references_asset",
                })
        return paths, refs

    def get_job(self, project_id: str, job_id: str) -> dict:
        record = self.generation_service.store.get(job_id)
        if record.project_id != project_id:
            raise AppError(404, "video_job_not_found", f"视频生成任务不存在: {job_id}")
        return self.generation_service.get_job(job_id)

    def get_current_version(self, project_id: str, shot_id: str):
        return self.versions.get_current(project_id, "shot_video", shot_id)
