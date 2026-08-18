"""Audio mix session persistence for the split audio pipeline."""

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


class AudioMixSessionRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def create(
        self,
        project_id: str,
        shot_id: str,
        *,
        stem_ids: list[str],
        gain_settings: dict | None = None,
        status: str = "draft",
    ) -> dict:
        session_id = _new_id("mix")
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO audio_mix_sessions (
                    id, project_id, shot_id, status, stem_snapshot,
                    gain_settings, output_audio_path, error, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?)
                """,
                (
                    session_id,
                    project_id,
                    shot_id,
                    status,
                    json.dumps(stem_ids, ensure_ascii=False),
                    json.dumps(gain_settings or {}, ensure_ascii=False),
                    now,
                    now,
                ),
            )
        return self.get(session_id)

    def update(
        self,
        session_id: str,
        *,
        status: str | None = None,
        output_audio_path: str | None = None,
        error: str | None = None,
    ) -> dict:
        with get_connection(self.db_path) as conn:
            if status is not None:
                conn.execute(
                    "UPDATE audio_mix_sessions SET status = ?, updated_at = ? WHERE id = ?",
                    (status, _now_iso(), session_id),
                )
            if output_audio_path is not None:
                conn.execute(
                    "UPDATE audio_mix_sessions SET output_audio_path = ?, updated_at = ? WHERE id = ?",
                    (output_audio_path, _now_iso(), session_id),
                )
            if error is not None:
                conn.execute(
                    "UPDATE audio_mix_sessions SET error = ?, updated_at = ? WHERE id = ?",
                    (error, _now_iso(), session_id),
                )
        return self.get(session_id)

    def get(self, session_id: str) -> dict:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM audio_mix_sessions WHERE id = ?",
                (session_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"audio mix session not found: {session_id}")
        return _session_out(row)

    def list_for_shot(self, project_id: str, shot_id: str) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM audio_mix_sessions
                WHERE project_id = ? AND shot_id = ?
                ORDER BY created_at DESC
                """,
                (project_id, shot_id),
            ).fetchall()
        return [_session_out(row) for row in rows]


def _session_out(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "shot_id": row["shot_id"],
        "status": row["status"],
        "stem_snapshot": _parse_json(row["stem_snapshot"], []),
        "gain_settings": _parse_json(row["gain_settings"], {}),
        "output_audio_path": row["output_audio_path"],
        "error": row["error"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
