"""Phase 13 M3 - Image Result Persistence.

图片 Job 完成后，把远端 URL / 本地临时文件下载到项目目录，写入 `versions`，
并补写 `production_edges`，避免只保存可能过期的厂商临时 URL。
"""

import subprocess
import uuid
from pathlib import Path
from urllib.parse import urlparse

import httpx

from app.core.errors import AppError
from app.services.asset_version_service import AssetVersionService
from app.services.adapters.base import GenerationResult
from app.services.media_mix import ffmpeg_exe
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
        "video/mp4": "mp4",
        "video/webm": "webm",
        "video/quicktime": "mov",
    }.get(normalized, "png")


class ImageResultService:
    def __init__(self, db_path, projects_dir) -> None:
        self.db_path = db_path
        self.projects_dir = Path(projects_dir)
        self.versions = AssetVersionService(db_path, projects_dir)
        self.graph = ProductionGraphService(db_path)

    def persist(self, job, result: GenerationResult) -> list:
        """把一次图片 GenerationResult 落为本地版本并写生产边。"""
        capability = getattr(job, "capability", "")
        extra = (job.input_payload or {}).get("extra") or {}
        target_type = extra.get("target_type")
        target_id = extra.get("target_id")
        if not target_type or not target_id:
            return []

        entity_type = self._entity_type_for_target(
            job.project_id, target_type, target_id, capability
        )
        records = []
        download_headers = getattr(result, "download_headers", None) or {}
        strip_audio = bool(extra.get("strip_audio"))
        is_video = capability in {"text_to_video", "image_to_video", "video_to_video"}
        for url in result.urls:
            file_bytes, source_path, file_ext = self._materialize(url, download_headers)
            if strip_audio and is_video and file_ext in {"mp4", "webm", "mov"}:
                source_path, file_ext = self._strip_audio(source_path, file_bytes, file_ext)
                file_bytes = None
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
                    "capability": capability,
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
            self._write_edges(
                job.project_id,
                target_type,
                target_id,
                record,
                extra,
                capability,
            )
        return records

    def _strip_audio(
        self, source_path: Path | None, file_bytes: bytes | None, file_ext: str
    ) -> tuple[Path, str]:
        """用 FFmpeg 移除视频音轨（-an），保证交付版本无声。"""
        tmp_dir = self.projects_dir / ".tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        input_path = source_path
        cleanup_input = False
        if input_path is None:
            input_path = tmp_dir / f"strip_in_{uuid.uuid4().hex[:8]}.{file_ext}"
            if file_bytes:
                input_path.write_bytes(file_bytes)
            cleanup_input = True
        output = tmp_dir / f"strip_{uuid.uuid4().hex[:12]}.{file_ext}"
        try:
            proc = subprocess.run(
                [
                    ffmpeg_exe(),
                    "-y",
                    "-i",
                    str(input_path),
                    "-an",
                    "-c:v",
                    "copy",
                    str(output),
                ],
                capture_output=True,
                text=True,
                timeout=180,
                check=False,
            )
        except Exception as exc:  # noqa: BLE001 - 统一转为业务错误
            raise AppError(
                500, "video_strip_audio_failed", "移除视频音轨失败（FFmpeg 不可用）"
            ) from exc
        finally:
            if cleanup_input and input_path.is_file():
                try:
                    input_path.unlink(missing_ok=True)
                except OSError:
                    pass
        if proc.returncode != 0 or not output.is_file():
            raise AppError(
                500,
                "video_strip_audio_failed",
                "移除视频音轨失败，无法生成无声版本",
            )
        return output, file_ext

    def _entity_type_for_target(
        self,
        project_id: str,
        target_type: str,
        target_id: str,
        capability: str = "",
    ) -> str:
        if target_type == "shot":
            return "shot_video" if capability in {"text_to_video", "image_to_video", "video_to_video"} else "shot"
        if target_type == "asset":
            for asset in StoryRepository(self.db_path).list_assets(project_id):
                if asset.get("asset_id") == target_id:
                    base = asset["asset_type"]
                    return (
                        f"{base}_video"
                        if capability in {"text_to_video", "image_to_video", "video_to_video"}
                        else base
                    )
            raise AppError(404, "asset_not_found", f"资产不存在: {target_id}")
        raise AppError(422, "invalid_image_target", f"未知图片目标类型: {target_type}")

    def _materialize(
        self, url: str, headers: dict | None = None
    ) -> tuple[bytes | None, Path | None, str]:
        path = Path(url)
        if path.is_absolute() and path.is_file():
            ext = path.suffix.lstrip(".") or "png"
            return None, path, ext
        if url.startswith(("http://", "https://")):
            try:
                with httpx.Client(timeout=60, follow_redirects=True) as client:
                    response = client.get(url, headers=headers or None)
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
        capability: str,
    ) -> None:
        upstream_type = "asset" if target_type == "asset" else "shot"
        is_video = capability in {"text_to_video", "image_to_video", "video_to_video"}
        version_type = "video_version" if is_video else "image_version"
        if target_type == "asset":
            relation = "video_generated_from_asset" if is_video else "image_generated_from_asset"
        else:
            relation = "video_generated_from_shot" if is_video else "image_generated_from_shot"
        self.graph.add_edge(
            project_id,
            upstream_type,
            target_id,
            version_type,
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
                version_type,
                record.id,
                relation=(
                    "video_generated_from_asset"
                    if is_video
                    else "image_generated_from_asset"
                ),
            )
