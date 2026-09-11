"""Phase 24 M1 — 剧集制作台聚合与零付费预检。"""

import json
from datetime import datetime, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection
from app.schemas.script import Scene, Shot
from app.services.capability_registry import IMAGE_CAPABILITIES, VIDEO_CAPABILITIES
from app.services.image_prompt_builder import build_shot_image_prompt
from app.services.production_graph import ProductionGraphService


ACTIVE_STATUSES = {"queued", "running", "paused"}


def build_episode_workspace(db_path: Path, project_id: str) -> dict:
    with get_connection(db_path) as conn:
        _ensure_project(conn, project_id)
        episodes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, title, order_index FROM episodes
                WHERE project_id = ? AND deleted_at IS NULL
                ORDER BY order_index, created_at
                """,
                (project_id,),
            ).fetchall()
        ]
        scenes = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, episode_id, title, slugline, action, order_index
                FROM scenes
                WHERE project_id = ? AND deleted_at IS NULL
                ORDER BY order_index, created_at
                """,
                (project_id,),
            ).fetchall()
        ]
        shots = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, scene_id, shot_number, order_index, characters, action,
                       dialogue, prompt
                FROM shots
                WHERE project_id = ? AND deleted_at IS NULL
                ORDER BY order_index, created_at
                """,
                (project_id,),
            ).fetchall()
        ]
        assets = [
            dict(row)
            for row in conn.execute(
                """
                SELECT id, asset_type, name FROM assets
                WHERE project_id = ? AND asset_type IN ('character', 'location', 'prop')
                ORDER BY created_at
                """,
                (project_id,),
            ).fetchall()
        ]
        current_versions = {
            (row["entity_type"], row["entity_id"]): row["id"]
            for row in conn.execute(
                """
                SELECT id, entity_type, entity_id FROM versions
                WHERE project_id = ? AND is_current = 1
                """,
                (project_id,),
            ).fetchall()
        }
        latest_jobs = _latest_shot_jobs(conn, project_id)
        reviews = _review_statuses(conn, project_id)

    health = ProductionGraphService(db_path).dependency_health(
        project_id, [value for (kind, _), value in current_versions.items() if kind in {"shot", "shot_video"}]
    )

    scene_by_id = {scene["id"]: scene for scene in scenes}
    shots_by_scene: dict[str, list[dict]] = {}
    for shot in shots:
        shots_by_scene.setdefault(shot["scene_id"], []).append(shot)
    scenes_by_episode: dict[str, list[dict]] = {}
    for scene in scenes:
        if scene["episode_id"]:
            scenes_by_episode.setdefault(scene["episode_id"], []).append(scene)

    result = []
    for episode in episodes:
        episode_scenes = scenes_by_episode.get(episode["id"], [])
        episode_shots = []
        for scene in episode_scenes:
            for shot in shots_by_scene.get(scene["id"], []):
                episode_shots.append(
                    _build_shot(
                        shot,
                        scene_by_id[shot["scene_id"]],
                        assets,
                        current_versions,
                        latest_jobs,
                        reviews,
                        health,
                    )
                )
        completed = sum(_shot_completed(item) for item in episode_shots)
        result.append(
            {
                "episode_id": episode["id"],
                "title": episode["title"],
                "order_index": episode["order_index"],
                "scene_count": len(episode_scenes),
                "shot_count": len(episode_shots),
                "completed_shots": completed,
                "attention_count": len(episode_shots) - completed,
                "stale_count": sum(any(item[f"{kind}_dependency_state"] in {"stale", "broken"} for kind in ("image", "video")) for item in episode_shots),
                "unknown_dependency_count": sum(any(issue["state"] == "unknown" for issue in item["dependency_issues"]) for item in episode_shots),
                "pinned_dependency_count": sum(any(issue["state"] == "pinned" for issue in item["dependency_issues"]) for item in episode_shots),
                "active_count": sum(
                    item["image_status"] == "active"
                    or item["video_status"] == "active"
                    for item in episode_shots
                ),
                "shots": episode_shots,
            }
        )
    return {"project_id": project_id, "episodes": result}


def prepare_episode(db_path: Path, project_id: str, episode_id: str) -> dict:
    filled_prompts = _fill_missing_prompts(db_path, project_id, episode_id)
    workspace = build_episode_workspace(db_path, project_id)
    episode = next(
        (item for item in workspace["episodes"] if item["episode_id"] == episode_id),
        None,
    )
    if episode is None:
        raise AppError(404, "episode_not_found", f"剧集不存在: {episode_id}")
    return {
        "episode": episode,
        "message": (
            f"预检完成：已补齐 {filled_prompts} 个缺失提示词；"
            "未创建生成任务，也不会产生模型费用。"
        ),
        "created_jobs": 0,
        "filled_prompts": filled_prompts,
    }


def _fill_missing_prompts(db_path: Path, project_id: str, episode_id: str) -> int:
    """只补齐可由现有剧本字段确定的空提示词，不覆盖用户内容。"""
    with get_connection(db_path) as conn:
        episode = conn.execute(
            """
            SELECT 1 FROM episodes
            WHERE id = ? AND project_id = ? AND deleted_at IS NULL
            """,
            (episode_id, project_id),
        ).fetchone()
        if episode is None:
            raise AppError(404, "episode_not_found", f"剧集不存在: {episode_id}")
        rows = conn.execute(
            """
            SELECT shots.*, scenes.title AS scene_title, scenes.slugline,
                   scenes.action AS scene_action, scenes.dialogue AS scene_dialogue,
                   scenes.order_index AS scene_order, scenes.novel_id AS scene_novel_id,
                   scenes.created_at AS scene_created_at,
                   scenes.updated_at AS scene_updated_at
            FROM shots
            JOIN scenes ON scenes.id = shots.scene_id
            WHERE shots.project_id = ? AND scenes.episode_id = ?
              AND shots.deleted_at IS NULL AND scenes.deleted_at IS NULL
              AND TRIM(shots.prompt) = ''
            ORDER BY shots.order_index
            """,
            (project_id, episode_id),
        ).fetchall()
        updates = []
        for row in rows:
            shot = Shot(
                id=row["id"],
                project_id=project_id,
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
            if not any(
                value.strip()
                for value in (
                    shot.shot_type,
                    shot.camera,
                    shot.characters,
                    shot.action,
                    shot.lighting,
                    shot.dialogue,
                )
            ):
                continue
            scene = Scene(
                id=row["scene_id"],
                project_id=project_id,
                episode_id=episode_id,
                novel_id=row["scene_novel_id"],
                title=row["scene_title"],
                order_index=row["scene_order"],
                slugline=row["slugline"],
                action=row["scene_action"],
                dialogue=row["scene_dialogue"],
                created_at=row["scene_created_at"],
                updated_at=row["scene_updated_at"],
            )
            updates.append((build_shot_image_prompt(shot, scene).prompt, row["id"]))
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        conn.executemany(
            "UPDATE shots SET prompt = ?, updated_at = ? WHERE id = ?",
            [(prompt, now, shot_id) for prompt, shot_id in updates],
        )
    return len(updates)


def _build_shot(shot, scene, assets, current_versions, latest_jobs, reviews, health) -> dict:
    script_ready = bool((shot["action"] or "").strip() or (shot["dialogue"] or "").strip())
    prompt_ready = bool((shot["prompt"] or "").strip())
    references = _matched_assets(shot, scene, assets, current_versions)
    missing_assets = [asset for asset in references if not asset["has_image"]]
    character_refs = [asset for asset in references if asset["asset_type"] == "character"]
    character_unmatched = bool((shot["characters"] or "").strip()) and not character_refs

    shot_id = shot["id"]
    has_image = ("shot", shot_id) in current_versions
    has_video = ("shot_video", shot_id) in current_versions
    image_status = _media_status(has_image, latest_jobs.get((shot_id, "image")))
    video_status = _media_status(has_video, latest_jobs.get((shot_id, "video")))
    review_status = reviews.get(shot_id, "pending" if has_image else "not_started")

    blockers = []
    dependency_states = {}
    dependency_issues = []
    for kind, entity_type in (("image", "shot"), ("video", "shot_video")):
        dependency = health.get(current_versions.get((entity_type, shot_id)), {"state": "none", "issues": []})
        dependency_states[f"{kind}_dependency_state"] = dependency["state"]
        for index, issue in enumerate(dependency["issues"]):
            dependency_issues.append({**issue, "media": kind})
            if issue["state"] in {"stale", "broken"}:
                blockers.append(_blocker(f"{kind}_dependency:{index}", issue["label"], "storyboard"))
        if dependency["state"] in {"stale", "broken"}:
            if kind == "image" and image_status == "ready":
                image_status = "stale"
            elif kind == "video" and video_status == "ready":
                video_status = "stale"
    if not script_ready:
        blockers.append(_blocker("script_missing", "缺少镜头动作或台词", "storyboard"))
    if character_unmatched:
        blockers.append(_blocker("character_unmatched", "角色未匹配到资产卡", "assets"))
    for asset in missing_assets:
        blockers.append(
            _blocker(
                f"asset_missing:{asset['asset_id']}",
                f"{_asset_type_label(asset['asset_type'])}「{asset['name']}」缺少参考图",
                "assets",
            )
        )
    if not prompt_ready:
        blockers.append(_blocker("prompt_missing", "缺少画面提示词", "storyboard"))
    if image_status == "failed":
        blockers.append(_blocker("image_failed", "关键帧生成失败", "storyboard"))
    elif not has_image and image_status != "active":
        blockers.append(_blocker("image_missing", "缺少关键帧", "storyboard"))
    if review_status == "flagged":
        blockers.append(_blocker("review_flagged", "质量审查存在异常", "storyboard"))
    elif has_image and review_status != "passed":
        blockers.append(_blocker("review_pending", "关键帧尚未通过审查", "storyboard"))
    if video_status == "failed":
        blockers.append(_blocker("video_failed", "视频生成失败", "storyboard"))
    elif not has_video and video_status != "active":
        blockers.append(_blocker("video_missing", "缺少镜头视频", "storyboard"))

    return {
        "shot_id": shot_id,
        "scene_id": shot["scene_id"],
        "scene_title": scene["slugline"] or scene["title"] or "未命名场景",
        "shot_number": shot["shot_number"],
        "order_index": shot["order_index"],
        "script_status": "ready" if script_ready else "missing",
        "asset_status": (
            "missing"
            if missing_assets or character_unmatched
            else "ready" if references else "not_referenced"
        ),
        "prompt_status": "ready" if prompt_ready else "missing",
        "image_status": image_status,
        "video_status": video_status,
        "review_status": review_status,
        **dependency_states,
        "dependency_issues": dependency_issues,
        "assets": references,
        "blockers": blockers,
    }


def _matched_assets(shot, scene, assets, current_versions) -> list[dict]:
    texts = {
        "character": shot["characters"] or "",
        "location": " ".join(
            (scene["slugline"] or "", scene["title"] or "", scene["action"] or "")
        ),
        "prop": " ".join(
            (shot["action"] or "", shot["dialogue"] or "", scene["action"] or "")
        ),
    }
    return [
        {
            "asset_id": asset["id"],
            "asset_type": asset["asset_type"],
            "name": asset["name"],
            "has_image": (asset["asset_type"], asset["id"]) in current_versions,
        }
        for asset in assets
        if asset["name"] and asset["name"] in texts[asset["asset_type"]]
    ]


def _media_status(has_version: bool, job: dict | None) -> str:
    if job and job["status"] in ACTIVE_STATUSES:
        return "active"
    if job and job["status"] == "failed" and not has_version:
        return "failed"
    return "ready" if has_version else "missing"


def _shot_completed(shot: dict) -> bool:
    return (
        shot["script_status"] == "ready"
        and shot["asset_status"] in {"ready", "not_referenced"}
        and shot["prompt_status"] == "ready"
        and shot["image_status"] == "ready"
        and shot["video_status"] == "ready"
        and shot["review_status"] == "passed"
    )


def _latest_shot_jobs(conn, project_id: str) -> dict[tuple[str, str], dict]:
    result = {}
    rows = conn.execute(
        """
        SELECT status, capability, input_payload FROM jobs
        WHERE project_id = ? ORDER BY created_at DESC
        """,
        (project_id,),
    ).fetchall()
    for row in rows:
        payload = _parse_json(row["input_payload"])
        extra = payload.get("extra") or {}
        if extra.get("target_type") != "shot" or not extra.get("target_id"):
            continue
        capability = row["capability"]
        kind = "image" if capability in IMAGE_CAPABILITIES else "video" if capability in VIDEO_CAPABILITIES else ""
        key = (extra["target_id"], kind)
        if kind and key not in result:
            result[key] = {"status": row["status"]}
    return result


def _review_statuses(conn, project_id: str) -> dict[str, str]:
    statuses: dict[str, list[str]] = {}
    for table, group_by_type in (
        ("shot_dialogue_reviews", False),
        ("shot_visual_reviews", True),
        ("story_consistency_reviews", False),
    ):
        seen = set()
        rows = conn.execute(
            f"SELECT shot_id, status{', review_type' if group_by_type else ''} "
            f"FROM {table} WHERE project_id = ? ORDER BY created_at DESC",
            (project_id,),
        ).fetchall()
        for row in rows:
            key = (row["shot_id"], row["review_type"]) if group_by_type else row["shot_id"]
            if key in seen:
                continue
            seen.add(key)
            statuses.setdefault(row["shot_id"], []).append(row["status"])
    return {
        shot_id: (
            "flagged"
            if "flagged" in values
            else "pending" if "pending" in values else "passed"
        )
        for shot_id, values in statuses.items()
    }


def _blocker(code: str, label: str, target: str) -> dict:
    return {"code": code, "label": label, "target": target}


def _asset_type_label(asset_type: str) -> str:
    return {"character": "角色", "location": "场景", "prop": "道具"}[asset_type]


def _parse_json(value: str | None) -> dict:
    try:
        return json.loads(value or "{}")
    except (TypeError, ValueError):
        return {}


def _ensure_project(conn, project_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM projects WHERE id = ? AND deleted_at IS NULL", (project_id,)
    ).fetchone()
    if row is None:
        raise AppError(404, "project_not_found", f"项目不存在: {project_id}")
