"""Phase 13 M2 - Image Generation Service.

负责把资产生图 / 分镜生图请求变成单个持久化 Generation Job。

一次请求只绑定一个模型 / 一个 Provider，不实现多模型并行。
"""

from app.core.errors import AppError
from app.schemas.script import Scene, Shot
from app.services.adapters.manager import ProviderManager
from app.services.capability_registry import IMAGE_CAPABILITIES
from app.services.generation_service import GenerationService
from app.services.image_prompt_builder import (
    build_asset_image_prompt,
    build_shot_image_prompt,
)
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository


class ImageGenerationService:
    def __init__(
        self,
        generation_service: GenerationService,
        provider_manager: ProviderManager,
        db_path,
    ) -> None:
        self.generation_service = generation_service
        self.provider_manager = provider_manager
        self.db_path = db_path

    def start_asset(
        self,
        project_id: str,
        asset_id: str,
        model_id: str,
        capability: str = "text_to_image",
        *,
        aspect_ratio: str | None = None,
        art_style: str | None = None,
        negative_prompt: str = "",
    ) -> dict:
        self._validate_capability(capability)
        asset = self._find_asset(project_id, asset_id)
        plan = build_asset_image_prompt(
            asset["asset_type"],
            asset.get("reference_prompt", ""),
            asset.get("fields") or {},
            aspect_ratio=aspect_ratio or None,
            art_style=art_style or None,
            source_refs=[
                {
                    "type": "asset",
                    "id": asset_id,
                    "relation": "image_generated_from_asset",
                }
            ],
        )
        return self._create_job(
            project_id=project_id,
            model_id=model_id,
            capability=capability,
            plan=plan,
            negative_prompt=negative_prompt,
            target_type="asset",
            target_id=asset_id,
        )

    def start_shot(
        self,
        project_id: str,
        shot_id: str,
        model_id: str,
        capability: str = "text_to_image",
        *,
        aspect_ratio: str | None = None,
        art_style: str | None = None,
        negative_prompt: str = "",
    ) -> dict:
        self._validate_capability(capability)
        shot, scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
        asset_references = self._resolve_shot_asset_references(
            project_id, shot, scene
        )
        source_refs = [
            {
                "type": "shot",
                "id": shot_id,
                "relation": "image_generated_from_shot",
            }
        ]
        source_refs.extend(
            {
                "type": "asset",
                "id": ref["id"],
                "relation": "shot_references_asset",
            }
            for ref in asset_references
        )
        plan = build_shot_image_prompt(
            shot,
            scene,
            asset_references=asset_references,
            aspect_ratio=aspect_ratio or None,
            art_style=art_style or None,
            source_refs=source_refs,
        )
        return self._create_job(
            project_id=project_id,
            model_id=model_id,
            capability=capability,
            plan=plan,
            negative_prompt=negative_prompt,
            target_type="shot",
            target_id=shot_id,
        )

    def get_job(self, project_id: str, job_id: str) -> dict:
        record = self.generation_service.store.get(job_id)
        if record.project_id != project_id:
            raise AppError(404, "image_job_not_found", f"图片生成任务不存在: {job_id}")
        return self.generation_service.get_job(job_id)

    def resolve_entity_type(
        self, project_id: str, target_type: str, target_id: str
    ) -> str:
        if target_type == "shot":
            return "shot"
        if target_type == "asset":
            return self._find_asset(project_id, target_id)["asset_type"]
        raise AppError(422, "invalid_image_target", f"未知图片目标类型: {target_type}")

    def _create_job(
        self,
        *,
        project_id: str,
        model_id: str,
        capability: str,
        plan,
        negative_prompt: str,
        target_type: str,
        target_id: str,
    ) -> dict:
        # Adapter 使用像素串作为尺寸，例如 OpenAI 兼容接口要求 1024x1536。
        size = f"{plan.width}x{plan.height}"
        return self.generation_service.create_job(
            model_id,
            capability,
            plan.prompt,
            aspect_ratio=size,
            project_id=project_id,
            negative_prompt=negative_prompt or plan.negative_prompt,
            extra={
                "target_type": target_type,
                "target_id": target_id,
                "width": plan.width,
                "height": plan.height,
                "source_refs": plan.source_refs,
            },
        )

    def _validate_capability(self, capability: str) -> None:
        if capability not in IMAGE_CAPABILITIES:
            raise AppError(
                422,
                "invalid_image_capability",
                f"未知图片能力: {capability}",
            )

    def _find_asset(self, project_id: str, asset_id: str) -> dict:
        for asset in StoryRepository(self.db_path).list_assets(project_id):
            if asset.get("asset_id") == asset_id:
                return asset
        raise AppError(404, "asset_not_found", f"资产不存在: {asset_id}")

    def _resolve_shot_asset_references(
        self, project_id: str, shot: Shot, scene: Scene
    ) -> list[dict]:
        """从 Story Bible 资产卡中找出镜头 / 场景明确提到的角色与地点。

        这是轻量匹配，只用于提示词一致性；不在这里做精确生产图绑定。
        """
        assets = StoryRepository(self.db_path).list_assets(project_id)
        references: list[dict] = []
        shot_text = shot.characters or ""
        scene_text = f"{scene.slugline or ''} {scene.action or ''}"
        for asset in assets:
            asset_type = asset["asset_type"]
            name = asset["name"]
            reference_prompt = asset.get("reference_prompt", "")
            if asset_type == "character" and name and name in shot_text:
                references.append(
                    {
                        "asset_type": "character",
                        "id": asset["asset_id"],
                        "name": name,
                        "reference_prompt": reference_prompt,
                    }
                )
            elif asset_type == "location" and name and name in scene_text:
                references.append(
                    {
                        "asset_type": "location",
                        "id": asset["asset_id"],
                        "name": name,
                        "reference_prompt": reference_prompt,
                    }
                )
        return references
