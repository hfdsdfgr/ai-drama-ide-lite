"""视觉一致性审核记录 Repository（shot_visual_reviews 表）。"""

import uuid
from datetime import datetime, timezone

from app.core.errors import AppError
from app.db.database import get_connection


def _new_id() -> str:
    return f"vrev_{uuid.uuid4().hex[:12]}"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _row_to_review(row) -> dict:
    return {
        "id": row["id"],
        "project_id": row["project_id"],
        "shot_id": row["shot_id"],
        "image_version_id": row["image_version_id"],
        "review_type": row["review_type"],
        "mode": row["mode"],
        "model_id": row["model_id"],
        "status": row["status"],
        "issue": row["issue"],
        "decision": row["decision"],
        "created_at": row["created_at"],
        "updated_at": row["updated_at"],
    }


class VisualReviewRepository:
    def __init__(self, db_path) -> None:
        self.db_path = db_path

    def create(
        self,
        project_id: str,
        shot_id: str,
        image_version_id: str,
        *,
        review_type: str,
        mode: str,
        model_id: str = "",
    ) -> dict:
        now = _now_iso()
        review_id = _new_id()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO shot_visual_reviews (
                    id, project_id, shot_id, image_version_id, review_type,
                    mode, model_id, status, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)
                """,
                (
                    review_id,
                    project_id,
                    shot_id,
                    image_version_id,
                    review_type,
                    mode,
                    model_id,
                    now,
                    now,
                ),
            )
        return self.get(review_id)

    def get(self, review_id: str) -> dict:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM shot_visual_reviews WHERE id = ?",
                (review_id,),
            ).fetchone()
        if row is None:
            raise AppError(404, "visual_review_not_found", f"视觉审核记录不存在：{review_id}")
        return _row_to_review(row)

    def list_for_shot(self, project_id: str, shot_id: str) -> list[dict]:
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                """
                SELECT * FROM shot_visual_reviews
                WHERE project_id = ? AND shot_id = ?
                ORDER BY created_at DESC
                """,
                (project_id, shot_id),
            ).fetchall()
        return [_row_to_review(row) for row in rows]

    def update_result(self, review_id: str, *, status: str, issue: str = "") -> dict:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE shot_visual_reviews
                SET status = ?, issue = ?, updated_at = ?
                WHERE id = ?
                """,
                (status, issue, _now_iso(), review_id),
            )
        return self.get(review_id)

    def update_decision(self, review_id: str, decision: str) -> dict:
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE shot_visual_reviews
                SET decision = ?, updated_at = ?
                WHERE id = ?
                """,
                (decision, _now_iso(), review_id),
            )
        return self.get(review_id)
