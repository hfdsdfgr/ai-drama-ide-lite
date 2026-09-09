"""外部视觉素材导入，统一接入版本与生产依赖图。"""

from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.services.asset_version_service import AssetVersionService
from app.services.production_graph import ProductionGraphService
from app.services.reference_media import ReferenceMediaRepository
from app.services.script_repo import ScriptRepository

IMAGE_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}
VIDEO_EXTENSIONS = {"mp4", "webm", "mov"}
MAX_IMAGE_BYTES = 25 * 1024 * 1024
MAX_VIDEO_BYTES = 500 * 1024 * 1024


def _extension(filename: str) -> str:
    return Path(filename or "").suffix.lstrip(".").lower()


class MediaImportService:
    def __init__(self, db_path: Path, projects_dir: Path) -> None:
        self.db_path = db_path
        self.versions = AssetVersionService(db_path, projects_dir)
        self.graph = ProductionGraphService(db_path)
        self.references = ReferenceMediaRepository(db_path)

    def import_asset_image(self, project_id: str, asset_id: str, filename: str, content: bytes):
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT asset_type FROM assets WHERE id = ? AND project_id = ?",
                (asset_id, project_id),
            ).fetchone()
        asset = dict(row) if row else None
        if asset is None:
            raise AppError(404, "asset_not_found", "资产不存在")
        return self._add(
            project_id, asset["asset_type"], asset_id, filename, content, "image", "asset", "image_imported_for_asset"
        )

    def import_shot_image(self, project_id: str, shot_id: str, filename: str, content: bytes):
        ScriptRepository(self.db_path).get_shot_with_scene(project_id, shot_id)
        return self._add(project_id, "shot", shot_id, filename, content, "image", "shot", "image_imported_for_shot")

    def import_shot_video(self, project_id: str, shot_id: str, filename: str, content: bytes):
        ScriptRepository(self.db_path).get_shot_with_scene(project_id, shot_id)
        return self._add(project_id, "shot_video", shot_id, filename, content, "video", "shot", "video_imported_for_shot")

    def import_reference_image(self, project_id: str, filename: str, content: bytes):
        self._validate(filename, content, "image")
        reference = self.references.create(project_id, Path(filename).stem)
        record = self.versions.add_version(
            project_id,
            "reference_image",
            reference["id"],
            file_bytes=content,
            file_ext=_extension(filename),
            payload={"source": "imported", "original_filename": filename},
        )
        self.graph.add_edge(project_id, "reference", reference["id"], "image_version", record.id, relation="reference_image_imported")
        return reference, record

    def _add(self, project_id: str, entity_type: str, entity_id: str, filename: str, content: bytes, kind: str, upstream_type: str, relation: str):
        self._validate(filename, content, kind)
        record = self.versions.add_version(
            project_id,
            entity_type,
            entity_id,
            file_bytes=content,
            file_ext=_extension(filename),
            payload={"source": "imported", "original_filename": filename},
        )
        self.graph.add_edge(project_id, upstream_type, entity_id, "video_version" if kind == "video" else "image_version", record.id, relation=relation)
        return record

    @staticmethod
    def _validate(filename: str, content: bytes, kind: str) -> None:
        ext = _extension(filename)
        allowed = IMAGE_EXTENSIONS if kind == "image" else VIDEO_EXTENSIONS
        limit = MAX_IMAGE_BYTES if kind == "image" else MAX_VIDEO_BYTES
        if ext not in allowed:
            label = "PNG / JPG / WebP" if kind == "image" else "MP4 / WebM / MOV"
            raise AppError(422, "invalid_media_type", f"请上传 {label} 文件")
        if not content:
            raise AppError(422, "media_empty", "文件为空")
        if len(content) > limit:
            raise AppError(422, "media_too_large", f"文件超过 {limit // 1024 // 1024}MB 限制")
