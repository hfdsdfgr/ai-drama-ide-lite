"""SQLite 项目仓储（Phase 1，取代 Phase 0 的 JSON 直写）。"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.core.logging import get_logger
from app.db.database import get_connection
from app.schemas.project import Project, ProjectCreate, ProjectUpdate
from app.services.project_files import ensure_project_layout

logger = get_logger("projects")

PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def new_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


def _row_to_project(row) -> Project:
    return Project(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


class ProjectRepository:
    def __init__(self, db_path: Path, projects_dir: Path) -> None:
        self.db_path = db_path
        self.projects_dir = projects_dir

    def _validate_id(self, project_id: str) -> None:
        if not PROJECT_ID_PATTERN.fullmatch(project_id):
            raise AppError(422, "invalid_project_id", "项目 ID 不合法")

    def create(self, data: ProjectCreate) -> Project:
        now = _now_iso()
        project = Project(
            id=new_project_id(),
            name=data.name.strip(),
            description=data.description.strip(),
            created_at=now,
            updated_at=now,
        )
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO projects (id, name, description, created_at, updated_at, deleted_at)"
                " VALUES (?, ?, ?, ?, ?, NULL)",
                (project.id, project.name, project.description, now, now),
            )
        ensure_project_layout(self.projects_dir / project.id)
        return project

    def list(self) -> list[Project]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, name, description, created_at, updated_at FROM projects"
                " WHERE deleted_at IS NULL ORDER BY updated_at DESC"
            ).fetchall()
        return [_row_to_project(row) for row in rows]

    def get(self, project_id: str) -> Project:
        self._validate_id(project_id)
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, name, description, created_at, updated_at FROM projects"
                " WHERE id = ? AND deleted_at IS NULL",
                (project_id,),
            ).fetchone()
        if row is None:
            raise AppError(404, "project_not_found", f"项目不存在: {project_id}")
        return _row_to_project(row)

    def update(self, project_id: str, data: ProjectUpdate) -> Project:
        project = self.get(project_id)
        payload = data.model_dump(exclude_unset=True)
        name = payload["name"].strip() if "name" in payload else project.name
        description = (
            payload["description"].strip() if "description" in payload else project.description
        )
        updated_at = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE projects SET name = ?, description = ?, updated_at = ? WHERE id = ?",
                (name, description, updated_at, project_id),
            )
        return Project(
            id=project.id,
            name=name,
            description=description,
            created_at=project.created_at,
            updated_at=updated_at,
        )

    def soft_delete(self, project_id: str) -> None:
        self.get(project_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE projects SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), project_id),
            )


def migrate_legacy_json_projects(db_path: Path, projects_dir: Path) -> None:
    """把 Phase 0 的 JSON 项目文件一次性迁入 SQLite，成功后归档原文件。"""
    if not projects_dir.exists():
        return
    archive_dir = projects_dir / ".archive"
    with get_connection(db_path) as conn:
        for path in sorted(projects_dir.glob("*.json")):
            try:
                legacy = Project.model_validate_json(path.read_text(encoding="utf-8"))
            except Exception:
                logger.warning("跳过损坏的旧项目文件: %s", path.name)
                continue
            exists = conn.execute(
                "SELECT 1 FROM projects WHERE id = ?", (legacy.id,)
            ).fetchone()
            if exists is None:
                conn.execute(
                    "INSERT INTO projects (id, name, description, created_at, updated_at, deleted_at)"
                    " VALUES (?, ?, ?, ?, ?, NULL)",
                    (
                        legacy.id,
                        legacy.name,
                        legacy.description,
                        _iso(legacy.created_at),
                        _iso(legacy.updated_at),
                    ),
                )
                logger.info("迁移旧项目: %s (%s)", legacy.name, legacy.id)
            archive_dir.mkdir(exist_ok=True)
            path.rename(archive_dir / path.name)
