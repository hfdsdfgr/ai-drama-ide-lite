"""Novel / Chapter 仓储（SQLite）。"""

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.novel import (
    Chapter,
    ChapterCreate,
    ChapterUpdate,
    Novel,
    NovelCreate,
    NovelDetail,
    NovelUpdate,
)

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _now_iso() -> str:
    return _iso(datetime.now(timezone.utc))


def _validate_id(value: str, label: str) -> None:
    if not ID_PATTERN.fullmatch(value):
        raise AppError(422, "invalid_id", f"{label} ID 不合法")


class NovelRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def _project_exists(self, conn, project_id: str) -> bool:
        return (
            conn.execute(
                "SELECT 1 FROM projects WHERE id = ? AND deleted_at IS NULL",
                (project_id,),
            ).fetchone()
            is not None
        )

    def create(
        self, project_id: str, data: NovelCreate, source_type: str = "original"
    ) -> Novel:
        _validate_id(project_id, "项目")
        now = _now_iso()
        novel_id = _new_id("novel")
        with get_connection(self.db_path) as conn:
            if not self._project_exists(conn, project_id):
                raise AppError(404, "project_not_found", f"项目不存在: {project_id}")
            conn.execute(
                "INSERT INTO novels (id, project_id, title, content, source_type, deleted_at, created_at, updated_at)"
                " VALUES (?, ?, ?, '', ?, NULL, ?, ?)",
                (novel_id, project_id, data.title.strip(), source_type, now, now),
            )
        return self.get(project_id, novel_id).novel

    def create_with_chapters(
        self,
        project_id: str,
        title: str,
        source_type: str,
        chapters: list[tuple[str, str]],
    ) -> Novel:
        _validate_id(project_id, "项目")
        now = _now_iso()
        novel_id = _new_id("novel")
        with get_connection(self.db_path) as conn:
            if not self._project_exists(conn, project_id):
                raise AppError(404, "project_not_found", f"项目不存在: {project_id}")
            conn.execute(
                "INSERT INTO novels (id, project_id, title, content, source_type, deleted_at, created_at, updated_at)"
                " VALUES (?, ?, ?, '', ?, NULL, ?, ?)",
                (novel_id, project_id, title.strip(), source_type, now, now),
            )
            for index, (chapter_title, content) in enumerate(chapters):
                conn.execute(
                    "INSERT INTO chapters (id, project_id, novel_id, title, content, order_index, deleted_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                    (
                        _new_id("chapter"),
                        project_id,
                        novel_id,
                        chapter_title.strip(),
                        content,
                        index,
                        now,
                        now,
                    ),
                )
        return self.get(project_id, novel_id).novel

    def list_novels(self, project_id: str, q: str = "") -> list[Novel]:
        _validate_id(project_id, "项目")
        pattern = f"%{q.strip()}%"
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT DISTINCT n.id, n.project_id, n.title, n.source_type, n.ai_brief, n.created_at, n.updated_at,
                       (SELECT COUNT(*) FROM chapters c
                         WHERE c.novel_id = n.id AND c.deleted_at IS NULL) AS chapter_count
                FROM novels n
                LEFT JOIN chapters c ON c.novel_id = n.id AND c.deleted_at IS NULL
                WHERE n.project_id = ? AND n.deleted_at IS NULL
                  AND (? = '' OR n.title LIKE ? OR c.title LIKE ? OR c.content LIKE ?)
                ORDER BY n.updated_at DESC
                """,
                (project_id, pattern, pattern, pattern, pattern),
            ).fetchall()
        return [_row_to_novel(row) for row in rows]

    def get(self, project_id: str, novel_id: str) -> NovelDetail:
        _validate_id(project_id, "项目")
        _validate_id(novel_id, "小说")
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT n.id, n.project_id, n.title, n.source_type, n.ai_brief, n.created_at, n.updated_at,"
                " (SELECT COUNT(*) FROM chapters c WHERE c.novel_id = n.id AND c.deleted_at IS NULL) AS chapter_count"
                " FROM novels n WHERE n.id = ? AND n.project_id = ? AND n.deleted_at IS NULL",
                (novel_id, project_id),
            ).fetchone()
            if row is None:
                raise AppError(404, "novel_not_found", f"小说不存在: {novel_id}")
            chapter_rows = conn.execute(
                "SELECT id, novel_id, title, content, order_index, created_at, updated_at"
                " FROM chapters WHERE novel_id = ? AND deleted_at IS NULL ORDER BY order_index, created_at",
                (novel_id,),
            ).fetchall()
        return NovelDetail(
            novel=_row_to_novel(row),
            chapters=[_row_to_chapter(r) for r in chapter_rows],
        )

    def update(self, project_id: str, novel_id: str, data: NovelUpdate) -> Novel:
        detail = self.get(project_id, novel_id)
        title = data.title.strip() if data.title is not None else detail.novel.title
        ai_brief = (
            data.ai_brief.strip()
            if data.ai_brief is not None
            else detail.novel.ai_brief
        )
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE novels SET title = ?, ai_brief = ?, updated_at = ? WHERE id = ?",
                (title, ai_brief, _now_iso(), novel_id),
            )
        return self.get(project_id, novel_id).novel

    def soft_delete(self, project_id: str, novel_id: str) -> None:
        self.get(project_id, novel_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE novels SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), novel_id),
            )

    def create_chapter(self, project_id: str, novel_id: str, data: ChapterCreate) -> Chapter:
        self.get(project_id, novel_id)
        now = _now_iso()
        chapter_id = _new_id("chapter")
        with get_connection(self.db_path) as conn:
            max_order = conn.execute(
                "SELECT COALESCE(MAX(order_index), -1) FROM chapters WHERE novel_id = ?",
                (novel_id,),
            ).fetchone()[0]
            conn.execute(
                "INSERT INTO chapters (id, project_id, novel_id, title, content, order_index, deleted_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    chapter_id,
                    project_id,
                    novel_id,
                    data.title.strip(),
                    data.content or "",
                    max_order + 1,
                    now,
                    now,
                ),
            )
        return self.get_chapter(novel_id, chapter_id)

    def get_chapter(self, novel_id: str, chapter_id: str) -> Chapter:
        _validate_id(chapter_id, "章节")
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, novel_id, title, content, order_index, created_at, updated_at"
                " FROM chapters WHERE id = ? AND deleted_at IS NULL",
                (chapter_id,),
            ).fetchone()
        if row is None:
            raise AppError(404, "chapter_not_found", f"章节不存在: {chapter_id}")
        return _row_to_chapter(row)

    def update_chapter(
        self, project_id: str, novel_id: str, chapter_id: str, data: ChapterUpdate
    ) -> Chapter:
        self.get(project_id, novel_id)
        chapter = self.get_chapter(novel_id, chapter_id)
        payload = data.model_dump(exclude_unset=True)
        title = payload["title"].strip() if "title" in payload else chapter.title
        content = payload["content"] if "content" in payload else chapter.content
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE chapters SET title = ?, content = ?, updated_at = ? WHERE id = ?",
                (title, content, _now_iso(), chapter_id),
            )
        return self.get_chapter(novel_id, chapter_id)

    def soft_delete_chapter(self, project_id: str, novel_id: str, chapter_id: str) -> None:
        self.get(project_id, novel_id)
        self.get_chapter(novel_id, chapter_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE chapters SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), chapter_id),
            )

    def restore(self, project_id: str, novels: list[dict]) -> None:
        """导入时恢复小说与章节（生成新 ID）。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            for item in novels:
                novel_id = _new_id("novel")
                conn.execute(
                    "INSERT INTO novels (id, project_id, title, content, source_type, deleted_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, '', ?, NULL, ?, ?)",
                    (
                        novel_id,
                        project_id,
                        str(item.get("title", "未命名小说")).strip(),
                        str(item.get("source_type", "original")),
                        now,
                        now,
                    ),
                )
                for index, chapter_data in enumerate(item.get("chapters", [])):
                    conn.execute(
                        "INSERT INTO chapters (id, project_id, novel_id, title, content, order_index, deleted_at, created_at, updated_at)"
                        " VALUES (?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                        (
                            _new_id("chapter"),
                            project_id,
                            novel_id,
                            str(chapter_data.get("title", "")).strip(),
                            str(chapter_data.get("content", "")),
                            index,
                            now,
                            now,
                        ),
                    )


def _row_to_novel(row) -> Novel:
    return Novel(
        id=row["id"],
        project_id=row["project_id"],
        title=row["title"],
        source_type=row["source_type"],
        ai_brief=row["ai_brief"] or "",
        chapter_count=row["chapter_count"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_chapter(row) -> Chapter:
    return Chapter(
        id=row["id"],
        novel_id=row["novel_id"],
        title=row["title"],
        content=row["content"],
        order_index=row["order_index"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
