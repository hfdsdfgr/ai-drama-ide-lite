"""项目导出 / 导入（zip + manifest，防 zip-slip）。"""

import io
import json
import shutil
import zipfile
from pathlib import Path, PurePosixPath

from app.core.errors import AppError
from app.schemas.project import ProjectCreate
from app.services.project_files import ensure_project_layout
from app.services.project_repo import ProjectRepository
from app.services.novel_repo import NovelRepository

MANIFEST_NAME = "project.json"
SCHEMA_VERSION = 2
MAX_ZIP_ENTRIES = 10_000


def _manifest(project, novel_repo: NovelRepository | None) -> dict:
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
    return {
        "schema_version": SCHEMA_VERSION,
        "project": {
            "name": project.name,
            "description": project.description,
        },
        "novels": novels,
    }


def export_project_zip(
    project, project_dir: Path, novel_repo: NovelRepository | None = None
) -> bytes:
    """导出为 zip：project.json manifest + files/ 文件树。"""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(
            MANIFEST_NAME,
            json.dumps(_manifest(project, novel_repo), ensure_ascii=False, indent=2),
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
            if manifest.get("schema_version") not in (1, SCHEMA_VERSION):
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
            if manifest.get("novels"):
                novel_repo = NovelRepository(repo.db_path)
                novel_repo.restore(project.id, manifest["novels"])
            return project
    except zipfile.BadZipFile as exc:
        raise AppError(422, "import_invalid_zip", "不是有效的 zip 文件") from exc
    except AppError:
        raise
    except Exception as exc:
        raise AppError(500, "import_failed", "导入失败") from exc
