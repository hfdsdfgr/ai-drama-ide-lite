"""Phase 9 — 资产版本服务。

职责：资产图片的版本化存储（每次 AI 生成都是新版本，绝不覆盖已有版本）。

版本文件落盘到 projects/{project_id}/assets/{asset_id}/v{n}.{ext}；
versions 表保存完整 recipe（模型 / 提示词 / 参数 / 来源 Job / 文件路径）。
每个资产只有一个 current 版本；恢复（promote）即切换 current；删除仅限非 current 版本。
"""

import json
import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_json(value: str | None, default) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


@dataclass
class AssetVersionRecord:
    id: str
    project_id: str
    entity_type: str
    entity_id: str
    version: int
    payload: dict
    file_path: str
    model_id: str
    provider_id: str
    job_id: str
    is_current: bool
    created_at: str


def _row_to_record(row) -> AssetVersionRecord:
    return AssetVersionRecord(
        id=row["id"],
        project_id=row["project_id"],
        entity_type=row["entity_type"],
        entity_id=row["entity_id"],
        version=row["version"],
        payload=_parse_json(row["payload"], {}),
        file_path=row["file_path"],
        model_id=row["model_id"],
        provider_id=row["provider_id"],
        job_id=row["job_id"],
        is_current=bool(row["is_current"]),
        created_at=row["created_at"],
    )


class AssetVersionService:
    def __init__(self, db_path: Path, projects_dir: Path) -> None:
        self.db_path = db_path
        self.projects_dir = projects_dir

    def _asset_dir(self, project_id: str, asset_id: str) -> Path:
        return self.projects_dir / project_id / "assets" / asset_id

    def add_version(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
        *,
        source_path: Path | str | None = None,
        file_bytes: bytes | None = None,
        file_ext: str = "png",
        model_id: str = "",
        provider_id: str = "",
        job_id: str = "",
        payload: dict | None = None,
    ) -> AssetVersionRecord:
        """新增一个版本：写文件 + 落 versions 记录 + 设为 current + 同步 assets.version。"""
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT COALESCE(MAX(version), 0) + 1 AS next_version
                FROM versions
                WHERE entity_type = ? AND entity_id = ?
                """,
                (entity_type, entity_id),
            ).fetchone()
        next_version = int(row["next_version"])

        asset_dir = self._asset_dir(project_id, entity_id)
        asset_dir.mkdir(parents=True, exist_ok=True)
        target = asset_dir / f"v{next_version}.{file_ext}"
        if source_path is not None:
            shutil.copyfile(str(source_path), target)
        elif file_bytes is not None:
            target.write_bytes(file_bytes)
        else:
            raise AppError(422, "version_file_required", "新增版本需要提供图片文件")

        now = _now_iso()
        version_id = _new_id("ver")
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE versions SET is_current = 0
                WHERE entity_type = ? AND entity_id = ? AND is_current = 1
                """,
                (entity_type, entity_id),
            )
            conn.execute(
                """
                INSERT INTO versions (
                    id, project_id, entity_type, entity_id, version,
                    payload, file_path, model_id, provider_id, job_id,
                    is_current, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
                """,
                (
                    version_id,
                    project_id,
                    entity_type,
                    entity_id,
                    next_version,
                    json.dumps(payload or {}, ensure_ascii=False),
                    str(target),
                    model_id,
                    provider_id,
                    job_id,
                    now,
                ),
            )
            conn.execute(
                "UPDATE assets SET version = ?, updated_at = ? WHERE id = ?",
                (next_version, now, entity_id),
            )
        return self.get(version_id)

    def get(self, version_id: str) -> AssetVersionRecord:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM versions WHERE id = ?", (version_id,)
            ).fetchone()
        if row is None:
            raise AppError(404, "version_not_found", f"资产版本不存在: {version_id}")
        return _row_to_record(row)

    def list_versions(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
    ) -> list[AssetVersionRecord]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM versions
                WHERE project_id = ? AND entity_type = ? AND entity_id = ?
                ORDER BY version DESC
                """,
                (project_id, entity_type, entity_id),
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    def get_current(
        self,
        project_id: str,
        entity_type: str,
        entity_id: str,
    ) -> AssetVersionRecord | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                """
                SELECT * FROM versions
                WHERE project_id = ? AND entity_type = ? AND entity_id = ?
                  AND is_current = 1
                """,
                (project_id, entity_type, entity_id),
            ).fetchone()
        return _row_to_record(row) if row else None

    def promote(self, version_id: str) -> AssetVersionRecord:
        """把指定版本设为 current（原 current 降级，不删文件）。"""
        record = self.get(version_id)
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE versions SET is_current = 0
                WHERE entity_type = ? AND entity_id = ? AND is_current = 1
                """,
                (record.entity_type, record.entity_id),
            )
            conn.execute(
                "UPDATE versions SET is_current = 1 WHERE id = ?",
                (version_id,),
            )
            conn.execute(
                "UPDATE assets SET version = ?, updated_at = ? WHERE id = ?",
                (record.version, now, record.entity_id),
            )
        return self.get(version_id)

    def delete(self, version_id: str) -> None:
        """删除一个非 current 版本（删记录 + 删文件）；当前版本不允许删除。"""
        record = self.get(version_id)
        if record.is_current:
            raise AppError(
                422,
                "current_version_cannot_delete",
                "当前版本不能删除，请先切换其他版本为当前",
            )
        path = Path(record.file_path)
        with get_connection(self.db_path) as conn:
            conn.execute("DELETE FROM versions WHERE id = ?", (version_id,))
        if path.is_file():
            path.unlink(missing_ok=True)
