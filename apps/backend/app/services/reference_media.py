"""项目级图片参考图库。"""

import uuid
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import get_connection


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id() -> str:
    return f"ref_{uuid.uuid4().hex[:12]}"


class ReferenceMediaRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = Path(db_path)

    def create(self, project_id: str, name: str) -> dict:
        record = {"id": _new_id(), "project_id": project_id, "name": name.strip() or "未命名参考图", "created_at": _now_iso()}
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO reference_media (id, project_id, name, created_at) VALUES (?, ?, ?, ?)",
                (record["id"], record["project_id"], record["name"], record["created_at"]),
            )
        return record

    def list(self, project_id: str) -> list[dict]:
        if not self.db_path.exists():
            return []
        try:
            with get_connection(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT id, project_id, name, created_at FROM reference_media WHERE project_id = ? ORDER BY created_at DESC",
                    (project_id,),
                ).fetchall()
        except sqlite3.OperationalError:
            return []
        return [dict(row) for row in rows]

    def get(self, project_id: str, reference_id: str) -> dict | None:
        if not self.db_path.exists():
            return None
        try:
            with get_connection(self.db_path) as conn:
                row = conn.execute(
                    "SELECT id, project_id, name, created_at FROM reference_media WHERE project_id = ? AND id = ?",
                    (project_id, reference_id),
                ).fetchone()
        except sqlite3.OperationalError:
            return None
        return dict(row) if row else None
