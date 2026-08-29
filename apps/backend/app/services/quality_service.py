"""项目级质量报告：聚合每个镜头的台词审核与视觉一致性审核结果。

每个镜头状态：
- flagged：存在任意一项异常（台词 / 角色 / 场景 / 连续性）；
- passed：已审核且全部通过；
- pending：有分镜图但没有任何审核记录；
- 无分镜图：不参与统计。
"""

from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection

REVIEW_TYPES = ("character", "scene", "continuity", "costume")


def build_project_quality(db_path: Path, project_id: str) -> dict:
    with get_connection(db_path) as conn:
        _ensure_project(conn, project_id)
        shots = _list_shots(conn, project_id)
        scene_titles = _scene_titles(conn, project_id)
        dialogue_reviews = _latest_reviews_by_shot(
            conn, project_id, "shot_dialogue_reviews"
        )
        visual_reviews = _latest_reviews_by_shot(
            conn, project_id, "shot_visual_reviews", group_by_type=True
        )
        story_reviews = _latest_reviews_by_shot(
            conn, project_id, "story_consistency_reviews"
        )
        images = _shot_image_flags(conn, project_id)

    items = []
    summary = {"flagged": 0, "passed": 0, "pending": 0, "total": 0}
    for shot in shots:
        has_image = shot["id"] in images
        dialogue = dialogue_reviews.get(shot["id"])
        visuals = visual_reviews.get(shot["id"], {})
        reviews = []
        if dialogue:
            reviews.append(dialogue)
        reviews.extend(visuals.values())
        if shot["id"] in story_reviews:
            reviews.append(story_reviews[shot["id"]])

        item = {
            "shot_id": shot["id"],
            "shot_number": shot["shot_number"],
            "order_index": shot["order_index"],
            "scene_title": scene_titles.get(shot["scene_id"], ""),
            "has_image": has_image,
            "status": "pending",
            "reviews": reviews,
        }
        if reviews:
            if any(r["status"] == "flagged" for r in reviews):
                item["status"] = "flagged"
                summary["flagged"] += 1
            else:
                item["status"] = "passed"
                summary["passed"] += 1
        elif has_image:
            item["status"] = "pending"
            summary["pending"] += 1
        if has_image or reviews:
            summary["total"] += 1
        items.append(item)

    items.sort(key=lambda item: (item["scene_title"], item["order_index"]))
    return {
        "project_id": project_id,
        "summary": summary,
        "items": items,
    }


def _ensure_project(conn, project_id: str) -> None:
    row = conn.execute(
        "SELECT 1 FROM projects WHERE id = ? AND deleted_at IS NULL",
        (project_id,),
    ).fetchone()
    if row is None:
        raise AppError(404, "project_not_found", f"项目不存在：{project_id}")


def _list_shots(conn, project_id: str) -> list[dict]:
    rows = conn.execute(
        """
        SELECT id, scene_id, shot_number, order_index
        FROM shots
        WHERE project_id = ? AND deleted_at IS NULL
        ORDER BY scene_id, order_index
        """,
        (project_id,),
    ).fetchall()
    return [dict(row) for row in rows]


def _scene_titles(conn, project_id: str) -> dict[str, str]:
    rows = conn.execute(
        """
        SELECT id, title, slugline FROM scenes
        WHERE project_id = ? AND deleted_at IS NULL
        """,
        (project_id,),
    ).fetchall()
    return {row["id"]: (row["slugline"] or row["title"] or "") for row in rows}


def _latest_reviews_by_shot(
    conn, project_id: str, table: str, *, group_by_type: bool = False
) -> dict:
    """返回 {shot_id: review}；group_by_type 时返回 {shot_id: {type: review}}。"""
    result: dict[str, dict] = {}
    rows = conn.execute(
        f"""
        SELECT * FROM {table}
        WHERE project_id = ?
        ORDER BY created_at DESC
        """,
        (project_id,),
    ).fetchall()
    seen: set[str] = set()
    for row in rows:
        key = (row["shot_id"], row["review_type"]) if group_by_type else row["shot_id"]
        if key in seen:
            continue
        seen.add(key)
        review = dict(row)
        if group_by_type:
            result.setdefault(row["shot_id"], {})[row["review_type"]] = review
        else:
            result[row["shot_id"]] = review
    return result


def _shot_image_flags(conn, project_id: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT entity_id FROM versions
        WHERE project_id = ? AND entity_type = 'shot' AND is_current = 1
        """,
        (project_id,),
    ).fetchall()
    return {row["entity_id"] for row in rows}
