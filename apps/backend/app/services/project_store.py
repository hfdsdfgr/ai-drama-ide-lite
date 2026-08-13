"""Minimal JSON-file project store.

Phase 0 占位实现：满足「创建 / 保存 / 重新打开 Project」的完成标准。
Phase 1 将替换为 SQLite 持久化（见 ROADMAP.md Phase 1）。
"""

import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.schemas.project import Project, ProjectCreate, ProjectUpdate

PROJECT_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _new_project_id() -> str:
    return f"proj_{uuid.uuid4().hex[:12]}"


class ProjectStore:
    def __init__(self, projects_dir: Path) -> None:
        self.projects_dir = projects_dir

    def _path(self, project_id: str) -> Path:
        if not PROJECT_ID_PATTERN.fullmatch(project_id):
            raise AppError(422, "invalid_project_id", "项目 ID 不合法")
        return self.projects_dir / f"{project_id}.json"

    def create(self, data: ProjectCreate) -> Project:
        now = datetime.now(timezone.utc)
        project = Project(
            id=_new_project_id(),
            name=data.name.strip(),
            description=data.description.strip(),
            created_at=now,
            updated_at=now,
        )
        self.projects_dir.mkdir(parents=True, exist_ok=True)
        self._path(project.id).write_text(
            project.model_dump_json(indent=2), encoding="utf-8"
        )
        return project

    def list(self) -> list[Project]:
        if not self.projects_dir.exists():
            return []
        projects: list[Project] = []
        for path in sorted(self.projects_dir.glob("*.json")):
            try:
                projects.append(Project.model_validate_json(path.read_text(encoding="utf-8")))
            except Exception:
                # 跳过损坏文件，不影响其他项目（Phase 1 将引入更严格的恢复机制）
                continue
        return projects

    def get(self, project_id: str) -> Project:
        path = self._path(project_id)
        if not path.exists():
            raise AppError(404, "project_not_found", f"项目不存在: {project_id}")
        try:
            return Project.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise AppError(500, "project_corrupted", f"项目文件损坏: {project_id}") from exc

    def update(self, project_id: str, data: ProjectUpdate) -> Project:
        project = self.get(project_id)
        payload = data.model_dump(exclude_unset=True)
        if "name" in payload:
            project.name = payload["name"].strip()
        if "description" in payload:
            project.description = payload["description"].strip()
        project.updated_at = datetime.now(timezone.utc)
        self._path(project_id).write_text(
            project.model_dump_json(indent=2), encoding="utf-8"
        )
        return project
