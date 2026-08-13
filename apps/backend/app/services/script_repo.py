"""剧本引擎仓储（Episode / Scene / Shot，Phase 7）。"""

import re
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.script import (
    Episode,
    EpisodeCreate,
    EpisodeDetail,
    Scene,
    SceneCreate,
    SceneDetail,
    Shot,
    ShotCreate,
)

ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _validate_id(value: str, label: str) -> None:
    if not ID_PATTERN.fullmatch(value):
        raise AppError(422, "invalid_id", f"{label} ID 不合法")


class ScriptRepository:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # ---------- Episode ----------

    def create_episode(
        self,
        project_id: str,
        data: EpisodeCreate,
        novel_id: str | None = None,
    ) -> Episode:
        _validate_id(project_id, "项目")
        now = _now_iso()
        episode_id = _new_id("episode")
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO episodes (id, project_id, novel_id, title, summary, order_index, source_chapter_index, deleted_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    episode_id,
                    project_id,
                    novel_id,
                    data.title.strip(),
                    data.summary.strip(),
                    data.order_index,
                    data.source_chapter_index,
                    now,
                    now,
                ),
            )
        return self.get_episode(project_id, episode_id)

    def list_episodes(
        self, project_id: str, novel_id: str | None = None
    ) -> list[Episode]:
        _validate_id(project_id, "项目")
        params: list = [project_id]
        where = "deleted_at IS NULL"
        if novel_id:
            where += " AND novel_id = ?"
            params.append(novel_id)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, project_id, novel_id, title, summary, order_index, source_chapter_index, created_at, updated_at"
                f" FROM episodes WHERE {where} ORDER BY order_index, created_at",
                params,
            ).fetchall()
        return [_row_to_episode(r) for r in rows]

    def get_episode(self, project_id: str, episode_id: str) -> Episode:
        _validate_id(project_id, "项目")
        _validate_id(episode_id, "分集")
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, project_id, novel_id, title, summary, order_index, source_chapter_index, created_at, updated_at"
                " FROM episodes WHERE id = ? AND project_id = ? AND deleted_at IS NULL",
                (episode_id, project_id),
            ).fetchone()
        if row is None:
            raise AppError(404, "episode_not_found", f"分集不存在: {episode_id}")
        return _row_to_episode(row)

    def get_episode_detail(self, project_id: str, episode_id: str) -> EpisodeDetail:
        episode = self.get_episode(project_id, episode_id)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, created_at, updated_at"
                " FROM scenes WHERE episode_id = ? AND deleted_at IS NULL ORDER BY order_index, created_at",
                (episode_id,),
            ).fetchall()
        return EpisodeDetail(
            episode=episode,
            scenes=[_row_to_scene(r) for r in rows],
        )

    def soft_delete_episode(self, project_id: str, episode_id: str) -> None:
        self.get_episode(project_id, episode_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE episodes SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), episode_id),
            )

    def save_episode_script(
        self,
        project_id: str,
        novel_id: str,
        source_chapter_index: int | None,
        episode_title: str,
        episode_summary: str,
        scenes: list[SceneCreate],
    ) -> EpisodeDetail:
        """事务保存一个分集及其全部场景。"""
        _validate_id(project_id, "项目")
        now = _now_iso()
        episode_id = _new_id("episode")
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO episodes (id, project_id, novel_id, title, summary, order_index, source_chapter_index, deleted_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    episode_id,
                    project_id,
                    novel_id,
                    episode_title.strip(),
                    episode_summary.strip(),
                    source_chapter_index if source_chapter_index is not None else 0,
                    source_chapter_index,
                    now,
                    now,
                ),
            )
            for index, scene in enumerate(scenes):
                conn.execute(
                    "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                    (
                        _new_id("scene"),
                        project_id,
                        episode_id,
                        novel_id,
                        scene.title.strip(),
                        scene.order_index if scene.order_index else index,
                        scene.slugline.strip(),
                        scene.action.strip(),
                        scene.dialogue.strip(),
                        now,
                        now,
                    ),
                )
        return self.get_episode_detail(project_id, episode_id)

    # ---------- Scene ----------

    def create_scene(
        self, project_id: str, episode_id: str, data: SceneCreate
    ) -> Scene:
        episode = self.get_episode(project_id, episode_id)
        now = _now_iso()
        scene_id = _new_id("scene")
        with get_connection(self.db_path) as conn:
            conn.execute(
                "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                (
                    scene_id,
                    project_id,
                    episode_id,
                    episode.novel_id,
                    data.title.strip(),
                    data.order_index,
                    data.slugline.strip(),
                    data.action.strip(),
                    data.dialogue.strip(),
                    now,
                    now,
                ),
            )
        return self.get_scene(project_id, scene_id)

    def get_scene(self, project_id: str, scene_id: str) -> Scene:
        _validate_id(project_id, "项目")
        _validate_id(scene_id, "场景")
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, created_at, updated_at"
                " FROM scenes WHERE id = ? AND project_id = ? AND deleted_at IS NULL",
                (scene_id, project_id),
            ).fetchone()
        if row is None:
            raise AppError(404, "scene_not_found", f"场景不存在: {scene_id}")
        return _row_to_scene(row)

    def get_scene_detail(self, project_id: str, scene_id: str) -> SceneDetail:
        scene = self.get_scene(project_id, scene_id)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                "SELECT id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, created_at, updated_at"
                " FROM shots WHERE scene_id = ? AND deleted_at IS NULL ORDER BY order_index, created_at",
                (scene_id,),
            ).fetchall()
        return SceneDetail(
            scene=scene,
            shots=[_row_to_shot(r) for r in rows],
        )

    def soft_delete_scene(self, project_id: str, scene_id: str) -> None:
        self.get_scene(project_id, scene_id)
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE scenes SET deleted_at = ?, updated_at = ? WHERE id = ?",
                (_now_iso(), _now_iso(), scene_id),
            )

    # ---------- Shot ----------

    def save_scene_shots(
        self, project_id: str, scene_id: str, shots: list[ShotCreate]
    ) -> SceneDetail:
        """事务保存一个场景的全部镜头。"""
        scene = self.get_scene(project_id, scene_id)
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            for index, shot in enumerate(shots):
                conn.execute(
                    "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at)"
                    " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, NULL, ?, ?)",
                    (
                        _new_id("shot"),
                        project_id,
                        scene_id,
                        shot.shot_number or index + 1,
                        shot.order_index if shot.order_index else index,
                        shot.shot_type.strip(),
                        shot.camera.strip(),
                        shot.characters.strip(),
                        shot.action.strip(),
                        shot.lighting.strip(),
                        shot.dialogue.strip(),
                        shot.duration,
                        shot.prompt.strip(),
                        now,
                        now,
                    ),
                )
        return self.get_scene_detail(project_id, scene_id)

    def soft_delete_shot(self, project_id: str, scene_id: str, shot_id: str) -> None:
        self.get_scene(project_id, scene_id)
        _validate_id(shot_id, "镜头")
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE shots SET deleted_at = ?, updated_at = ? WHERE id = ? AND scene_id = ?",
                (_now_iso(), _now_iso(), shot_id, scene_id),
            )


def _row_to_episode(row: sqlite3.Row) -> Episode:
    return Episode(
        id=row["id"],
        project_id=row["project_id"],
        novel_id=row["novel_id"],
        title=row["title"],
        summary=row["summary"],
        order_index=row["order_index"],
        source_chapter_index=row["source_chapter_index"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_scene(row: sqlite3.Row) -> Scene:
    return Scene(
        id=row["id"],
        project_id=row["project_id"],
        episode_id=row["episode_id"],
        novel_id=row["novel_id"],
        title=row["title"],
        order_index=row["order_index"],
        slugline=row["slugline"],
        action=row["action"],
        dialogue=row["dialogue"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def _row_to_shot(row: sqlite3.Row) -> Shot:
    return Shot(
        id=row["id"],
        project_id=row["project_id"],
        scene_id=row["scene_id"],
        shot_number=row["shot_number"],
        order_index=row["order_index"],
        shot_type=row["shot_type"],
        camera=row["camera"],
        characters=row["characters"],
        action=row["action"],
        lighting=row["lighting"],
        dialogue=row["dialogue"],
        duration=row["duration"],
        prompt=row["prompt"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )
