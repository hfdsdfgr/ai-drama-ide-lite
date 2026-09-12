"""Phase 13 M2 - Image Generation Service.

负责把资产生图 / 分镜生图请求变成单个持久化 Generation Job。

一次请求只绑定一个模型 / 一个 Provider，不实现多模型并行。
"""

import uuid
from pathlib import Path

from app.core.errors import AppError
from app.schemas.script import Scene, Shot
from app.services.adapters.manager import ProviderManager
from app.services.asset_version_service import AssetVersionService
from app.services.reference_media import ReferenceMediaRepository
from app.services.capability_registry import IMAGE_CAPABILITIES
from app.services.generation_service import GenerationService
from app.services.image_prompt_builder import (
    build_asset_image_prompt,
    build_shot_image_prompt,
)
from app.services.job_store import TERMINAL_STATUSES
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository


class ImageGenerationService:
    def __init__(
        self,
        generation_service: GenerationService,
        provider_manager: ProviderManager,
        db_path,
        asset_version_service: AssetVersionService,
    ) -> None:
        self.generation_service = generation_service
        self.provider_manager = provider_manager
        self.db_path = db_path
        self.asset_version_service = asset_version_service

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
        reference_asset_ids: list[str] | None = None,
        reference_version_ids: list[str] | None = None,
        pinned_version_ids: list[str] | None = None,
        prompt: str | None = None,
        regenerated_from_version_id: str | None = None,
        batch_id: str = "",
        batch_label: str = "",
        target_label: str = "",
    ) -> dict:
        explicit_versions = reference_version_ids is not None
        reference_asset_ids = reference_asset_ids or []
        reference_version_ids = reference_version_ids or []
        pinned = set(pinned_version_ids or [])
        if not pinned.issubset(reference_version_ids):
            raise AppError(422, "invalid_pinned_reference", "固定版本必须是本次选择的参考版本")
        if reference_asset_ids and reference_version_ids:
            raise AppError(422, "ambiguous_reference_input", "参考资产与参考版本不能同时提交")
        if (reference_asset_ids or reference_version_ids) and capability == "text_to_image":
            capability = self._reference_capability(model_id)
        self._validate_capability(capability)
        shot, scene = ScriptRepository(self.db_path).get_shot_with_scene(
            project_id, shot_id
        )
        if regenerated_from_version_id:
            original = self.asset_version_service.get(regenerated_from_version_id)
            if (original.project_id, original.entity_type, original.entity_id) != (project_id, "shot", shot_id):
                raise AppError(422, "invalid_regeneration_source", "重新生成的来源版本不属于当前镜头")
        if prompt is not None:
            shot = shot.model_copy(update={"prompt": prompt})
        asset_references = self._resolve_shot_asset_references(
            project_id, shot, scene, reference_asset_ids
        ) if not explicit_versions else []
        asset_references = self._attach_reference_versions(
            project_id, asset_references, reference_version_ids
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
                "entity_type": ref["asset_type"],
                "version_id": ref["version_id"],
                "version": ref["version"],
                "selection_mode": "historical" if ref["version_id"] in pinned else "current",
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
            batch_id=batch_id,
            batch_label=batch_label,
            target_label=target_label,
            images=self._reference_image_paths(asset_references),
            user_prompt=shot.prompt or shot.action or "",
            regenerated_from_version_id=regenerated_from_version_id or "",
        )

    def get_job(self, project_id: str, job_id: str) -> dict:
        record = self.generation_service.store.get(job_id)
        if record.project_id != project_id:
            raise AppError(404, "image_job_not_found", f"图片生成任务不存在: {job_id}")
        return self.generation_service.get_job(job_id)

    def plan_shots(self, project_id: str, model_id: str, shot_ids: list[str]) -> dict:
        """预检批量关键帧：不创建 Job，也不调用外部模型。"""
        self.provider_manager.adapter_for(model_id, "text_to_image")
        active = self._active_shot_ids(project_id)
        ready: list[dict] = []
        skipped: list[dict] = []
        seen: set[str] = set()
        repo = ScriptRepository(self.db_path)

        for shot_id in shot_ids:
            if shot_id in seen:
                continue
            seen.add(shot_id)
            try:
                shot, scene = repo.get_shot_with_scene(project_id, shot_id)
                label = f"{scene.title or scene.slugline or '场景'} · 镜头 {shot.shot_number or '-'}"
                if shot_id in active:
                    skipped.append({"shot_id": shot_id, "label": label, "reason": "已有进行中的图片任务"})
                    continue
                if self.asset_version_service.get_current(project_id, "shot", shot_id):
                    skipped.append({"shot_id": shot_id, "label": label, "reason": "已有当前关键帧版本"})
                    continue
                references = self._resolve_shot_asset_references(project_id, shot, scene)
                self._reference_image_paths(
                    self._attach_reference_versions(project_id, references, [])
                )
                ready.append({"shot_id": shot_id, "label": label})
            except AppError as exc:
                skipped.append({"shot_id": shot_id, "label": f"镜头 {shot_id}", "reason": exc.message})
        return {"ready": ready, "skipped": skipped}

    def start_shots(
        self,
        project_id: str,
        model_id: str,
        shot_ids: list[str],
        batch_label: str = "批量关键帧",
    ) -> dict:
        """为预检通过的镜头逐个创建独立 Job，失败项不影响其余镜头。"""
        plan = self.plan_shots(project_id, model_id, shot_ids)
        batch_id = f"batch_{uuid.uuid4().hex[:12]}"
        jobs: list[dict] = []
        skipped = list(plan["skipped"])
        for item in plan["ready"]:
            try:
                jobs.append(
                    self.start_shot(
                        project_id,
                        item["shot_id"],
                        model_id,
                        batch_id=batch_id,
                        batch_label=batch_label,
                        target_label=item["label"],
                    )
                )
            except AppError as exc:
                skipped.append({**item, "reason": exc.message})
        return {
            "batch_id": batch_id,
            "jobs": jobs,
            "ready": plan["ready"],
            "skipped": skipped,
        }

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
        batch_id: str = "",
        batch_label: str = "",
        target_label: str = "",
        images: list[str] | None = None,
        user_prompt: str = "",
        regenerated_from_version_id: str = "",
    ) -> dict:
        self.provider_manager.validate_declared_parameters(
            model_id,
            capability,
            {"aspect_ratio": plan.aspect_ratio},
        )
        # Adapter 使用像素串作为尺寸，例如 OpenAI 兼容接口要求 1024x1536。
        size = f"{plan.width}x{plan.height}"
        return self.generation_service.create_job(
            model_id,
            capability,
            plan.prompt,
            aspect_ratio=size,
            project_id=project_id,
            images=images or [],
            negative_prompt=negative_prompt or plan.negative_prompt,
            extra={
                "target_type": target_type,
                "target_id": target_id,
                "batch_id": batch_id,
                "batch_label": batch_label,
                "target_label": target_label,
                "width": plan.width,
                "height": plan.height,
                "source_refs": plan.source_refs,
                "user_prompt": user_prompt,
                "regenerated_from_version_id": regenerated_from_version_id,
            },
        )

    def _validate_capability(self, capability: str) -> None:
        if capability not in IMAGE_CAPABILITIES:
            raise AppError(
                422,
                "invalid_image_capability",
                f"未知图片能力: {capability}",
            )

    def _active_shot_ids(self, project_id: str) -> set[str]:
        active: set[str] = set()
        for job in self.generation_service.store.list_jobs(project_id, limit=500):
            if job.status in TERMINAL_STATUSES or job.capability not in IMAGE_CAPABILITIES:
                continue
            extra = (job.input_payload or {}).get("extra") or {}
            if extra.get("target_type") == "shot" and extra.get("target_id"):
                active.add(extra["target_id"])
        return active

    def _find_asset(self, project_id: str, asset_id: str) -> dict:
        for asset in StoryRepository(self.db_path).list_assets(project_id):
            if asset.get("asset_id") == asset_id:
                return asset
        reference = ReferenceMediaRepository(self.db_path).get(project_id, asset_id)
        if reference:
            return {
                "asset_id": reference["id"],
                "asset_type": "reference_image",
                "name": reference["name"],
                "reference_prompt": "",
            }
        raise AppError(404, "asset_not_found", f"资产不存在: {asset_id}")

    def _reference_capability(self, model_id: str) -> str:
        model = self.provider_manager.repo.get_model(model_id)
        if "reference_image" in model.capabilities:
            return "reference_image"
        if "image_to_image" in model.capabilities:
            return "image_to_image"
        raise AppError(
            422,
            "reference_not_supported",
            f"模型 {model.model_id} 不支持参考图生图，请选择支持 reference_image 或 image_to_image 的模型",
        )

    def _reference_image_paths(self, references: list[dict]) -> list[str]:
        return [ref["file_path"] for ref in references]

    def _attach_reference_versions(
        self,
        project_id: str,
        references: list[dict],
        reference_version_ids: list[str],
    ) -> list[dict]:
        """Turn selected assets into immutable image-version references."""
        if reference_version_ids:
            resolved: list[dict] = []
            seen: set[str] = set()
            for version_id in reference_version_ids:
                if version_id in seen:
                    continue
                seen.add(version_id)
                record = self.asset_version_service.get(version_id)
                if record.project_id != project_id or record.entity_type not in {
                    "character", "location", "prop", "reference_image"
                }:
                    raise AppError(422, "invalid_reference_version", "参考图片版本不属于当前项目或类型不支持")
                if not record.file_path or not Path(record.file_path).is_file():
                    raise AppError(422, "reference_image_missing", "参考图片版本文件不存在")
                asset = self._find_asset(project_id, record.entity_id)
                resolved.append({
                    "asset_type": record.entity_type,
                    "id": record.entity_id,
                    "name": asset["name"],
                    "reference_prompt": asset.get("reference_prompt", ""),
                    "version_id": record.id,
                    "version": record.version,
                    "file_path": record.file_path,
                })
            return resolved

        resolved = []
        for ref in references:
            current = self.asset_version_service.get_current(project_id, ref["asset_type"], ref["id"])
            if current is None:
                raise AppError(422, "reference_image_missing", f"资产「{ref['name']}」还没有可用的图片版本，无法作为参考图")
            resolved.append({
                **ref,
                "version_id": getattr(current, "id", ""),
                "version": getattr(current, "version", None),
                "file_path": current.file_path,
            })
        return resolved

    def _resolve_shot_asset_references(
        self,
        project_id: str,
        shot: Shot,
        scene: Scene,
        reference_asset_ids: list[str] | None = None,
    ) -> list[dict]:
        """从 Story Bible 资产卡中找出镜头 / 场景明确提到的角色与地点。

        当用户明确选择参考资产时，优先使用这些资产；否则按文本做轻量匹配。
        """
        assets = StoryRepository(self.db_path).list_assets(project_id)
        references = [
            {
                "asset_id": item["id"],
                "asset_type": "reference_image",
                "name": item["name"],
                "reference_prompt": "",
            }
            for item in ReferenceMediaRepository(self.db_path).list(project_id)
        ]
        selectable = [*assets, *references]
        if reference_asset_ids:
            selected_ids = set(reference_asset_ids)
            selected = [
                asset
                for asset in selectable
                if asset["asset_id"] in selected_ids
            ]
            if len(selected) != len(selected_ids):
                missing = selected_ids - {asset["asset_id"] for asset in selected}
                raise AppError(
                    404,
                    "reference_asset_not_found",
                    f"参考资产不存在: {', '.join(sorted(missing))}",
                )
            return [
                {
                    "asset_type": asset["asset_type"],
                    "id": asset["asset_id"],
                    "name": asset["name"],
                    "reference_prompt": asset.get("reference_prompt", ""),
                }
                for asset in selected
            ]

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
