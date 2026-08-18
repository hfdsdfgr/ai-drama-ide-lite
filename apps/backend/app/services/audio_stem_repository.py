"""Audio stem persistence for the split audio pipeline."""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import get_connection


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_json(value: str | None, default) -> object:
    if not value:
        return default
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return default


class AudioStemRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def create(
        self,
        project_id: str,
        shot_id: str,
        *,
        role: str,
        source_type: str,
        file_path: str,
        format: str = "wav",
        duration: float = 0,
        model_id: str = "",
        provider_id: str = "",
        job_id: str = "",
        order_index: int = 0,
        payload: dict | None = None,
    ) -> dict:
        stem_id = _new_id("stem")
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audio_stems (
                    id, project_id, shot_id, role, source_type,
                    file_path, format, duration, model_id, provider_id,
                    job_id, order_index, payload, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    stem_id,
                    project_id,
                    shot_id,
                    role,
                    source_type,
                    file_path,
                    format,
                    duration,
                    model_id,
                    provider_id,
                    job_id,
                    order_index,
                    json.dumps(payload or {}, ensure_ascii=False),
                    now,
                ),
            )
        return self.get(stem_id)

    def get(self, stem_id: str) -> dict:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM audio_stems WHERE id = ?",
                (stem_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"audio stem not found: {stem_id}")
        return _stem_out(row)

    def list_for_shot(self, project_id: str, shot_id: str) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM audio_stems
                WHERE project_id = ? AND shot_id = ?
                ORDER BY order_index, created_at
                """,
                (project_id, shot_id),
            ).fetchall()
        return [_stem_out(row) for row in rows]


def _stem_out(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "shot_id": row["shot_id"],
        "role": row["role"],
        "source_type": row["source_type"],
        "file_path": row["file_path"],
        "format": row["format"],
        "duration": row["duration"],
        "model_id": row["model_id"],
        "provider_id": row["provider_id"],
        "job_id": row["job_id"],
        "order_index": row["order_index"],
        "payload": _parse_json(row["payload"], {}),
        "created_at": row["created_at"],
    }
