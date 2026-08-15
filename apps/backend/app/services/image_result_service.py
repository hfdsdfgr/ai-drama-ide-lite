"""Phase 13 M3 - Image Result Persistence.

图片 Job 完成后，把远端 URL / 本地临时文件下载到项目目录，写入 `versions`，
并补写 `production_edges`，避免只保存可能过期的厂商临时 URL。
"""

from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.errors import AppError
from app.services.asset_version_service import AssetVersionService
from app.services.adapters.base import GenerationResult
from app.services.production_graph import ProductionGraphService
from app.services.story_repo import ASSET_TYPES, StoryRepository


def _extension_from_content_type(content_type: str | None) -> str:
    if not content_type:
        return "png"
    normalized = content_type.split(";")[0].strip().lower()
    return {
        "image/jpeg": "jpg",
        "image/png": "png",
        "image/webp": "webp",
        "image/bmp": "bmp",
        "image/gif": "gif",
    }.get(normalized, "png")


class ImageResultService:
    def __init__(self, db_path, projects_dir) -> None:
        self.db_path = db_path
        self.versions = AssetVersionService(db_path, projects_dir)
        self.graph = ProductionGraphService(db_path)

    def persist(self, job, result: GenerationResult) -> list:
        """把一次图片 GenerationResult 落为本地版本并写生产边。"""
        extra = (job.input_payload or {}).get("extra") or {}
        target_type = extra.get("target_type")
        target_id = extra.get("target_id")
        if not target_type or not target_id:
            return []

        entity_type = self._entity_type_for_target(job.project_id, target_type, target_id)
        records = []
        for url in result.urls:
            file_bytes, source_path, file_ext = self._materialize(url)
            record = self.versions.add_version(
                job.project_id,
                entity_type,
                target_id,
                source_path=source_path,
                file_bytes=file_bytes,
                file_ext=file_ext,
                model_id=job.model_id,
                provider_id=job.provider_id,
                job_id=job.id,
                payload={
                    "prompt": (job.input_payload or {}).get("prompt", ""),
                    "negative_prompt": (job.input_payload or {}).get("negative_prompt", ""),
                    "aspect_ratio": (job.input_payload or {}).get("aspect_ratio", ""),
                    "source_url": url,
                    "target_type": target_type,
                    "target_id": target_id,
                    "source_refs": extra.get("source_refs", []),
                },
            )
            records.append(record)
            self._write_edges(job.project_id, target_type, target_id, record, extra)
        return records

    def _entity_type_for_target(
        self, project_id: str, target_type: str, target_id: str
    ) -> str:
        if target_type == "shot":
            return "shot"
        if target_type == "asset":
            for asset in StoryRepository(self.db_path).list_assets(project_id):
                if asset.get("asset_id") == target_id:
                    return asset["asset_type"]
            raise AppError(404, "asset_not_found", f"资产不存在: {target_id}")
        raise AppError(422, "invalid_image_target", f"未知图片目标类型: {target_type}")

    def _materialize(self, url: str) -> tuple[bytes | None, Path | None, str]:
        path = Path(url)
        if path.is_absolute() and path.is_file():
            ext = path.suffix.lstrip(".") or "png"
            return None, path, ext
        if url.startswith(("http://", "https://")):
            try:
                with httpx.Client(timeout=60, follow_redirects=True) as client:
                    response = client.get(url)
                    response.raise_for_status()
            except httpx.TimeoutException as exc:
                raise AppError(
                    504, "image_download_timeout", "图片结果下载超时，请稍后重试"
                ) from exc
            except httpx.HTTPStatusError as exc:
                raise AppError(
                    exc.response.status_code,
                    "image_download_failed",
                    f"图片结果下载失败（HTTP {exc.response.status_code}）",
                ) from exc
            except Exception as exc:
                raise AppError(
                    502,
                    "image_download_failed",
                    "无法下载图片结果，请检查网络后重试",
                ) from exc
            ext = _extension_from_content_type(response.headers.get("content-type"))
            return response.content, None, ext
        raise AppError(422, "image_url_invalid", f"图片结果地址无效: {url}")

    def _write_edges(
        self,
        project_id: str,
        target_type: str,
        target_id: str,
        record,
        extra: dict,
    ) -> None:
        upstream_type = "asset" if target_type == "asset" else "shot"
        relation = (
            "image_generated_from_asset"
            if target_type == "asset"
            else "image_generated_from_shot"
        )
        self.graph.add_edge(
            project_id,
            upstream_type,
            target_id,
            "image_version",
            record.id,
            relation=relation,
        )

        for ref in extra.get("source_refs", []):
            if ref.get("type") != "asset":
                continue
            ref_id = ref.get("id")
            if not ref_id:
                continue
            self.graph.add_edge(
                project_id,
                "asset",
                ref_id,
                "image_version",
                record.id,
                relation="image_generated_from_asset",
            )
