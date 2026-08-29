"""旧库 shot_visual_reviews 表迁移测试（CHECK 增加 costume）。"""

from app.db.database import get_connection, init_db


def test_migration_preserves_data_and_allows_costume(tmp_path):
    db_path = tmp_path / "test.db"
    # 构造旧版表（无 costume）
    import sqlite3

    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE shot_visual_reviews (
            id                 TEXT PRIMARY KEY,
            project_id         TEXT NOT NULL,
            shot_id            TEXT NOT NULL,
            image_version_id   TEXT NOT NULL,
            review_type        TEXT NOT NULL DEFAULT 'character' CHECK (review_type IN ('character', 'scene', 'continuity')),
            mode               TEXT NOT NULL DEFAULT 'manual' CHECK (mode IN ('model', 'manual')),
            model_id           TEXT NOT NULL DEFAULT '',
            status             TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'passed', 'flagged')),
            issue              TEXT NOT NULL DEFAULT '',
            decision           TEXT NOT NULL DEFAULT '' CHECK (decision IN ('', 'regenerate', 'delete_shot', 'keep')),
            created_at         TEXT NOT NULL,
            updated_at         TEXT NOT NULL
        );
        INSERT INTO shot_visual_reviews VALUES (
            'vr1', 'p', 'shot1', 'v1', 'character', 'manual', '',
            'flagged', '问题', '', '2026-08-16T00:00:00Z', '2026-08-16T00:00:00Z'
        );
        """
    )
    conn.close()

    init_db(db_path)

    with get_connection(db_path) as conn:
        # 旧数据保留
        row = conn.execute(
            "SELECT issue FROM shot_visual_reviews WHERE id = 'vr1'"
        ).fetchone()
        assert row["issue"] == "问题"
        # 新 CHECK 允许 costume
        conn.execute(
            "INSERT INTO shot_visual_reviews (id, project_id, shot_id, image_version_id, review_type, mode, model_id, status, issue, decision, created_at, updated_at) VALUES ('vr2', 'p', 'shot2', 'v2', 'costume', 'model', 'm', 'flagged', '服装', '', '2026-08-16T00:00:00Z', '2026-08-16T00:00:00Z')"
        )
