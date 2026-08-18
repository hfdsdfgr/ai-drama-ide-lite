"""DialogueClip persistence（Phase 14 M3）。"""

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.db.database import get_connection
from app.schemas.audio_timeline import (
    AlignmentResult,
    DialogueClip,
    DialogueClipSegment,
)


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


def _alignment_from_dict(data: dict | None) -> AlignmentResult | None:
    if not data:
        return None
    try:
        return AlignmentResult.model_validate(data)
    except Exception:  # noqa: BLE001 - 旧数据容错
        return None


def _segments_from_list(data: list) -> list[DialogueClipSegment]:
    segments: list[DialogueClipSegment] = []
    for item in data:
        try:
            segments.append(DialogueClipSegment.model_validate(item))
        except Exception:  # noqa: BLE001 - 旧数据容错
            continue
    return segments


class DialogueClipRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    def replace_for_shot(
        self,
        project_id: str,
        shot_id: str,
        clips: list[DialogueClip],
        *,
        job_id: str = "",
    ) -> list[dict]:
        """覆盖某个 Shot 的全部 DialogueClip（重跑配音时不残留旧时间轴）。"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "DELETE FROM dialogue_clips WHERE project_id = ? AND shot_id = ?",
                (project_id, shot_id),
            )
            for index, clip in enumerate(clips):
                now = _now_iso()
                clip_id = clip.id or _new_id("clip")
                conn.execute(
                    """
                    INSERT INTO dialogue_clips (
                        id, project_id, shot_id, audio_asset_id,
                        speaker_id, voice_profile_id, start_time, end_time,
                        version, alignment, segments, job_id, order_index,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        clip_id,
                        project_id,
                        shot_id,
                        clip.audio_asset_id,
                        clip.speaker_id,
                        clip.voice_profile_id,
                        clip.start_time,
                        clip.end_time,
                        clip.version,
                        json.dumps(
                            clip.alignment.model_dump() if clip.alignment else {},
                            ensure_ascii=False,
                        ),
                        json.dumps(
                            [s.model_dump() for s in clip.segments],
                            ensure_ascii=False,
                        ),
                        job_id,
                        index,
                        now,
                        now,
                    ),
                )
        return self.list_for_shot(project_id, shot_id)

    def list_for_shot(self, project_id: str, shot_id: str) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM dialogue_clips
                WHERE project_id = ? AND shot_id = ?
                ORDER BY order_index, created_at
                """,
                (project_id, shot_id),
            ).fetchall()
        return [_clip_out(row) for row in rows]

    def list_for_project(self, project_id: str) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM dialogue_clips
                WHERE project_id = ?
                ORDER BY shot_id, order_index, created_at
                """,
                (project_id,),
            ).fetchall()
        return [_clip_out(row) for row in rows]

    def get(self, clip_id: str) -> dict:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM dialogue_clips WHERE id = ?",
                (clip_id,),
            ).fetchone()
        if row is None:
            raise KeyError(f"dialogue clip not found: {clip_id}")
        return _clip_out(row)


def _clip_out(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "shot_id": row["shot_id"],
        "audio_asset_id": row["audio_asset_id"],
        "speaker_id": row["speaker_id"],
        "voice_profile_id": row["voice_profile_id"],
        "start_time": row["start_time"],
        "end_time": row["end_time"],
        "version": row["version"],
        "alignment": _alignment_from_dict(
            _parse_json(row["alignment"], None)
        ),
        "segments": _segments_from_list(_parse_json(row["segments"], [])),
        "job_id": row["job_id"],
        "order_index": row["order_index"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }
