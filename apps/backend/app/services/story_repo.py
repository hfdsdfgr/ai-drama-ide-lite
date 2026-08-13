"""Story Bible 读写（Phase 6）。

复用 Phase 1 基线 schema 的 stories / characters / locations / props 表。
实体同步策略：按 (project_id, name) upsert——新实体插入、已有实体更新描述；
不删除已有行（保护用户可能的手动数据）。完整覆盖式的清理留到后续明确需求。
"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import get_connection
from app.schemas.story import BibleCharacter, BibleLocation, BibleProp, StoryBible


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


class StoryRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def get_bible(self, project_id: str) -> StoryBible | None:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT content FROM stories WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
                (project_id,),
            ).fetchone()
        if row is None:
            return None
        try:
            data = json.loads(row["content"])
            return StoryBible(**data)
        except (ValueError, TypeError):
            return None

    def save_bible(self, project_id: str, bible: StoryBible) -> None:
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            existing = conn.execute(
                "SELECT id FROM stories WHERE project_id = ? LIMIT 1", (project_id,)
            ).fetchone()
            content = json.dumps(bible.model_dump(), ensure_ascii=False)
            if existing:
                conn.execute(
                    "UPDATE stories SET content = ?, updated_at = ? WHERE id = ?",
                    (content, now, existing["id"]),
                )
            else:
                conn.execute(
                    "INSERT INTO stories (id, project_id, content, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?)",
                    (_new_id("story"), project_id, content, now, now),
                )
            self._sync_entities(conn, project_id, "characters", bible.characters)
            self._sync_entities(conn, project_id, "locations", bible.locations)
            self._sync_entities(conn, project_id, "props", bible.props)

    @staticmethod
    def _sync_entities(
        conn,
        project_id: str,
        table: str,
        items: list[BibleCharacter | BibleLocation | BibleProp],
    ) -> None:
        prefix = {
            "characters": "char",
            "locations": "loc",
            "props": "prop",
        }[table]
        now = _now_iso()
        for item in items:
            description = getattr(item, "summary", None) or item.description
            if not description:
                description = ""
            existing = conn.execute(
                f"SELECT id FROM {table} WHERE project_id = ? AND name = ?",
                (project_id, item.name),
            ).fetchone()
            if existing:
                conn.execute(
                    f"UPDATE {table} SET description = ?, updated_at = ? WHERE id = ?",
                    (description, now, existing["id"]),
                )
            else:
                conn.execute(
                    f"INSERT INTO {table} (id, project_id, name, description, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?)",
                    (_new_id(prefix), project_id, item.name, description, now, now),
                )
