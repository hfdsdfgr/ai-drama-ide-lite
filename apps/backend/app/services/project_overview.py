"""Phase 15 — 项目生产阶段汇总服务。

把项目在整条生产链路上的进度汇总为固定顺序的阶段列表：
每个阶段只返回 `pending / active / completed` 三种状态和一句面向用户的简短说明。

阶段语义：
- 小说分析：项目已存在可分析的小说内容（有章节或正文）。
- Story Bible / 人物提取 / 剧本生成 / 分镜：对应数据已生成。
- 人物资产 / 场景资产 / 生图 / 图生视频：对应图片/视频版本已生成，
  且存在未结束的 Generation Job 时显示“进行中”。
"""

import json
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.services.capability_registry import IMAGE_CAPABILITIES, VIDEO_CAPABILITIES


ACTIVE_STATUSES = ("queued", "running", "paused")

STAGES: tuple[tuple[str, str], ...] = (
    ("novel_analysis", "小说分析"),
    ("story_bible", "Story Bible"),
    ("character_extraction", "人物提取"),
    ("script_generation", "剧本生成"),
    ("character_asset", "人物资产"),
    ("scene_asset", "场景资产"),
    ("storyboard", "分镜"),
    ("image_generation", "生图"),
    ("video_generation", "图生视频"),
)


def build_project_overview(db_path: Path, project_id: str) -> dict:
    with get_connection(db_path) as conn:
        _ensure_project(conn, project_id)
        snapshot = _snapshot(conn, project_id)
        active = _active_stages(conn, project_id)

    stages = []
    for key, label in STAGES:
        is_active = key in active
        if is_active:
            status = "active"
        elif snapshot[key] > 0:
            status = "completed"
        else:
            status = "pending"
        stages.append(
            {
                "key": key,
                "label": label,
                "status": status,
                "detail": _detail(key, snapshot, is_active),
            }
        )
    return {"project_id": project_id, "stages": stages}


def _ensure_project(conn, project_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM projects WHERE id = ? AND deleted_at IS NULL",
        (project_id,),
    ).fetchone()
    if row is None:
        raise AppError(404, "project_not_found", f"项目不存在: {project_id}")


def _snapshot(conn, project_id: str) -> dict[str, int]:
    novels = conn.execute(
        """
        SELECT COUNT(*) AS total,
               COALESCE(SUM(CASE WHEN content <> '' THEN 1 ELSE 0 END), 0) AS with_content
        FROM novels
        WHERE project_id = ? AND deleted_at IS NULL
        """,
        (project_id,),
    ).fetchone()
    chapters = _count(conn, "chapters", project_id, soft_delete=True)
    bible_ready = 1 if _bible_has_content(conn, project_id) else 0
    characters = _count(conn, "characters", project_id)
    episodes = _count(conn, "episodes", project_id, soft_delete=True)
    scenes = _count(conn, "scenes", project_id, soft_delete=True)
    shots = _count(conn, "shots", project_id, soft_delete=True)

    return {
        "novel_analysis": chapters if chapters else int(novels["with_content"]),
        "story_bible": bible_ready,
        "character_extraction": characters,
        "script_generation": episodes if episodes else scenes,
        "character_asset": _current_version_count(conn, project_id, "character"),
        "scene_asset": _current_version_count(conn, project_id, "location"),
        "storyboard": shots,
        "image_generation": _current_version_count(conn, project_id, "shot"),
        "video_generation": _any_version_count(conn, project_id, "shot_video"),
        # 用于 detail 展示，不参与完成度判断
        "_novels_with_content": int(novels["with_content"]),
        "_chapters": chapters,
        "_episodes": episodes,
        "_scenes": scenes,
        "_shots": shots,
    }


def _count(conn, table: str, project_id: str, soft_delete: bool = False) -> int:
    if soft_delete:
        sql = f"SELECT COUNT(*) AS c FROM {table} WHERE project_id = ? AND deleted_at IS NULL"
    else:
        sql = f"SELECT COUNT(*) AS c FROM {table} WHERE project_id = ?"
    return int(conn.execute(sql, (project_id,)).fetchone()["c"])


def _bible_has_content(conn, project_id: str) -> bool:
    row = conn.execute(
        "SELECT content FROM stories WHERE project_id = ? ORDER BY updated_at DESC LIMIT 1",
        (project_id,),
    ).fetchone()
    if row is None:
        return False
    try:
        data = json.loads(row["content"])
    except (ValueError, TypeError):
        return False
    keys = (
        "synopsis",
        "characters",
        "locations",
        "props",
        "events",
        "conflicts",
        "plotlines",
        "foreshadowing",
    )
    return any(bool(data.get(key)) for key in keys)


def _current_version_count(conn, project_id: str, entity_type: str) -> int:
    row = conn.execute(
        """
        SELECT COUNT(*) AS c FROM versions
        WHERE project_id = ? AND entity_type = ? AND is_current = 1
        """,
        (project_id, entity_type),
    ).fetchone()
    return int(row["c"])


def _any_version_count(conn, project_id: str, entity_type: str) -> int:
    row = conn.execute(
        "SELECT COUNT(*) AS c FROM versions WHERE project_id = ? AND entity_type = ?",
        (project_id, entity_type),
    ).fetchone()
    return int(row["c"])


def _active_stages(conn, project_id: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT capability, input_payload FROM jobs
        WHERE project_id = ? AND status IN (?, ?, ?)
        """,
        (project_id, *ACTIVE_STATUSES),
    ).fetchall()
    active: set[str] = set()
    for row in rows:
        capability = row["capability"]
        payload = _parse_json(row["input_payload"])
        extra = payload.get("extra") or {}
        target_type = extra.get("target_type")
        target_id = extra.get("target_id")

        if capability in IMAGE_CAPABILITIES:
            if target_type == "asset":
                asset_type = _asset_type(conn, target_id)
                if asset_type == "character":
                    active.add("character_asset")
                elif asset_type == "location":
                    active.add("scene_asset")
            elif target_type == "shot":
                active.add("image_generation")
        elif capability in VIDEO_CAPABILITIES:
            if target_type == "shot":
                active.add("video_generation")
    return active


def _asset_type(conn, asset_id: str) -> str:
    if not asset_id:
        return ""
    row = conn.execute(
        "SELECT asset_type FROM assets WHERE id = ?", (asset_id,)
    ).fetchone()
    return row["asset_type"] if row else ""


def _parse_json(value: str | None) -> dict:
    if not value:
        return {}
    try:
        return json.loads(value)
    except (ValueError, TypeError):
        return {}


def _detail(key: str, snapshot: dict[str, int], is_active: bool) -> str:
    if key == "novel_analysis":
        if snapshot["_chapters"]:
            return f"{snapshot['_chapters']} 章"
        return "1 部小说" if snapshot["_novels_with_content"] else ""
    if key == "story_bible":
        return "已生成" if snapshot["story_bible"] else ""
    if key == "character_extraction":
        return f"{snapshot['character_extraction']} 个角色" if snapshot["character_extraction"] else ""
    if key == "script_generation":
        parts = []
        if snapshot["_episodes"]:
            parts.append(f"{snapshot['_episodes']} 集")
        if snapshot["_scenes"]:
            parts.append(f"{snapshot['_scenes']} 场")
        return " · ".join(parts)
    if key == "storyboard":
        return f"{snapshot['_shots']} 个镜头" if snapshot["_shots"] else ""
    if key == "character_asset":
        return _generated_detail(snapshot["character_asset"], "个角色", is_active)
    if key == "scene_asset":
        return _generated_detail(snapshot["scene_asset"], "个场景", is_active)
    if key == "image_generation":
        return _generated_detail(snapshot["image_generation"], "张分镜图", is_active)
    if key == "video_generation":
        return _generated_detail(snapshot["video_generation"], "段视频", is_active)
    return ""


def _generated_detail(count: int, unit: str, is_active: bool) -> str:
    if is_active:
        return f"{count} {unit}已生成 · 生成中" if count else "生成中"
    return f"{count} {unit}已生成" if count else ""
