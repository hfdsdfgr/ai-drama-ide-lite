"""项目导出 / 导入（zip + manifest，防 zip-slip）。"""

import io
import json
import shutil
import uuid
import zipfile
from pathlib import Path, PurePosixPath

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.project import ProjectCreate
from app.services.project_files import ensure_project_layout
from app.services.project_repo import ProjectRepository
from app.services.novel_repo import NovelRepository

MANIFEST_NAME = "project.json"
SCHEMA_VERSION = 3
MAX_ZIP_ENTRIES = 10_000


SNAPSHOT_TABLES = (
    "novels", "chapters", "stories", "characters", "locations", "props",
    "episodes", "scenes", "shots", "assets", "reference_media", "versions",
    "production_edges", "shot_dialogue_reviews", "shot_visual_reviews",
    "story_consistency_reviews", "pipelines",
)


def _manifest(project, novel_repo: NovelRepository | None, db_path: Path | None) -> dict:
    novels: list[dict] = []
    if novel_repo is not None:
        for novel in novel_repo.list_novels(project.id):
            detail = novel_repo.get(project.id, novel.id)
            novels.append(
                {
                    "title": detail.novel.title,
                    "source_type": detail.novel.source_type,
                    "chapters": [
                        {"title": c.title, "content": c.content}
                        for c in detail.chapters
                    ],
                }
            )
    manifest = {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "name": project.name,
            "description": project.description,
        },
        "novels": novels,
    }
    if db_path is not None:
        manifest["snapshot"] = _export_snapshot(db_path, project.id)
    return manifest


def export_project_zip(
    project,
    project_dir: Path,
    novel_repo: NovelRepository | None = None,
    db_path: Path | None = None,
) -> bytes:
    """导出为 zip：project.json manifest + files/ 文件树。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            MANIFEST_NAME,
            json.dumps(_manifest(project, novel_repo, db_path), ensure_ascii=False, indent=2),
        )
        if project_dir.exists():
            for path in sorted(project_dir.rglob("*")):
                if path.is_file():
                    rel = path.relative_to(project_dir).as_posix()
                    zf.write(path, f"files/{rel}")
    return buffer.getvalue()


def _safe_zip_target(base_dir: Path, entry_name: str) -> Path | None:
    """校验 zip 条目路径，拒绝绝对路径、盘符与 ..（zip-slip 防护）。"""
    name = entry_name.replace("\\", "/")
    parts = PurePosixPath(name).parts
    if not parts or any(part in ("", ".", "..") for part in parts):
        return None
    if name.startswith("/") or len(parts) > 0 and ":" in parts[0]:
        return None
    try:
        target = (base_dir / name).resolve()
    except (OSError, ValueError):
        return None
    if not target.is_relative_to(base_dir.resolve()):
        return None
    return target


def import_project_zip(raw: bytes, repo: ProjectRepository) -> object:
    """导入 zip 为新项目（生成新 Project ID），失败时抛出 AppError。"""
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zf:
            entries = zf.namelist()
            if len(entries) > MAX_ZIP_ENTRIES:
                raise AppError(422, "import_too_large", "zip 条目过多")
            manifest_entry = next(
                (e for e in entries if e.replace("\\", "/") == MANIFEST_NAME), None
            )
            if manifest_entry is None:
                raise AppError(422, "import_invalid_manifest", "zip 缺少 project.json")
            manifest = json.loads(zf.read(manifest_entry))
            if manifest.get("schema_version") not in (1, 2, SCHEMA_VERSION):
                raise AppError(422, "import_version_unsupported", "不支持的 manifest 版本")
            data = manifest.get("project") or {}
            name = str(data.get("name", "")).strip()
            if not name:
                raise AppError(422, "import_invalid_manifest", "project.name 为空")
            project = repo.create(
                ProjectCreate(name=name, description=str(data.get("description", "")))
            )
            base = repo.projects_dir / project.id
            ensure_project_layout(base)
            for entry in entries:
                norm = entry.replace("\\", "/")
                if norm == MANIFEST_NAME or norm.endswith("/"):
                    continue
                if not norm.startswith("files/"):
                    raise AppError(422, "import_invalid_entry", f"未知条目: {entry}")
                rel = norm.removeprefix("files/")
                target = _safe_zip_target(base, rel)
                if target is None:
                    raise AppError(422, "import_invalid_path", "zip 包含非法路径")
                target.parent.mkdir(parents=True, exist_ok=True)
                with zf.open(entry) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
            if manifest.get("snapshot"):
                _restore_snapshot(repo.db_path, project.id, manifest["snapshot"], base)
            elif manifest.get("novels"):
                novel_repo = NovelRepository(repo.db_path)
                novel_repo.restore(project.id, manifest["novels"])
            return project
    except zipfile.BadZipFile as exc:
        raise AppError(422, "import_invalid_zip", "不是有效的 zip 文件") from exc
    except AppError:
        raise
    except Exception as exc:
        raise AppError(
            500, "import_failed", "导入失败，请查看后端日志后重试"
        ) from exc


def _export_snapshot(db_path: Path, project_id: str) -> dict:
    """导出项目级创作数据；Provider 与音频链路不在项目包内。"""
    result: dict[str, list[dict]] = {}
    with get_connection(db_path) as conn:
        for table in SNAPSHOT_TABLES:
            rows = conn.execute(
                f"SELECT * FROM {table} WHERE project_id = ?", (project_id,)
            ).fetchall()
            result[table] = [dict(row) for row in rows]
    return result


def _restore_snapshot(db_path: Path, project_id: str, snapshot: dict, project_dir: Path) -> None:
    """以新 ID 恢复项目快照，避免二次导入时主键冲突。"""
    records = {table: list(snapshot.get(table) or []) for table in SNAPSHOT_TABLES}
    id_maps: dict[str, dict[str, str]] = {}
    for table in SNAPSHOT_TABLES:
        if table == "pipelines":
            continue
        id_maps[table] = {
            str(row["id"]): f"{row['id']}_{uuid.uuid4().hex[:8]}"
            for row in records[table]
            if row.get("id")
        }

    def mapped(table: str, value: str | None) -> str | None:
        if value is None:
            return None
        return id_maps.get(table, {}).get(str(value), str(value))

    def entity_id(entity_type: str, value: str) -> str:
        if entity_type == "asset":
            return mapped("assets", value) or value
        if entity_type in {"image_version", "video_version"}:
            return mapped("versions", value) or value
        if entity_type in {"character", "location", "prop"}:
            return mapped("assets", value) or value
        if entity_type.startswith("shot"):
            return mapped("shots", value) or value
        if entity_type.startswith("scene"):
            return mapped("scenes", value) or value
        if entity_type.startswith("episode"):
            return mapped("episodes", value) or value
        if entity_type == "reference_image":
            return mapped("reference_media", value) or value
        if entity_type == "reference":
            return mapped("reference_media", value) or value
        return value

    all_maps = {
        old: new
        for table_map in id_maps.values()
        for old, new in table_map.items()
    }

    def remap_json(value: str) -> str:
        try:
            parsed = json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

        def walk(item):
            if isinstance(item, str):
                return all_maps.get(item, item)
            if isinstance(item, list):
                return [walk(x) for x in item]
            if isinstance(item, dict):
                return {key: walk(item_value) for key, item_value in item.items()}
            return item

        return json.dumps(walk(parsed), ensure_ascii=False)

    def rebase_path(value: str) -> str:
        path = Path(value)
        for parent in path.parents:
            if parent.name.startswith("proj_"):
                try:
                    return str(project_dir / path.relative_to(parent))
                except ValueError:
                    break
        return ""

    foreign_keys = {
        "chapters": {"novel_id": "novels"},
        "episodes": {"novel_id": "novels"},
        "scenes": {"episode_id": "episodes", "novel_id": "novels"},
        "shots": {"scene_id": "scenes"},
        "versions": {"job_id": "jobs"},
        "shot_dialogue_reviews": {"shot_id": "shots", "video_version_id": "versions"},
        "shot_visual_reviews": {"shot_id": "shots", "image_version_id": "versions"},
        "story_consistency_reviews": {"shot_id": "shots"},
    }

    insert_order = (
        "novels", "chapters", "stories", "characters", "locations", "props",
        "episodes", "scenes", "shots", "assets", "reference_media", "versions",
        "production_edges", "shot_dialogue_reviews", "shot_visual_reviews",
        "story_consistency_reviews", "pipelines",
    )
    with get_connection(db_path) as conn:
        for table in insert_order:
            for row in records[table]:
                data = dict(row)
                data["project_id"] = project_id
                if table != "pipelines":
                    data["id"] = mapped(table, data["id"])
                for column, target in foreign_keys.get(table, {}).items():
                    if data.get(column):
                        data[column] = mapped(target, data[column])
                if table == "stories":
                    data["content"] = remap_json(data["content"])
                if table == "versions":
                    data["entity_id"] = entity_id(data["entity_type"], data["entity_id"])
                    data["file_path"] = rebase_path(data["file_path"])
                    data["payload"] = remap_json(data["payload"])
                    data["job_id"] = ""
                if table == "production_edges":
                    data["upstream_id"] = entity_id(data["upstream_type"], data["upstream_id"])
                    data["downstream_id"] = entity_id(data["downstream_type"], data["downstream_id"])
                columns = list(data)
                placeholders = ", ".join("?" for _ in columns)
                conn.execute(
                    f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})",
                    [data[column] for column in columns],
                )
