"""SQLite 连接与初始化。

迁移策略：schema.sql 全部使用 IF NOT EXISTS（幂等），
schema_migrations 记录已应用的版本，后续加列按
DEVELOPMENT_PITFALLS.md 记录的 try/except ALTER TABLE 模式扩展。
"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.logging import get_logger

logger = get_logger("db")

_SCHEMA_PATH = Path(__file__).with_name("schema.sql")


def get_connection(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(str(db_path), timeout=30)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


def init_db(db_path: Path) -> None:
    """创建数据库并应用基线 schema（幂等）。"""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    schema = _SCHEMA_PATH.read_text(encoding="utf-8")
    with get_connection(db_path) as conn:
        conn.executescript(schema)
        _apply_safe_migrations(conn)
        _backfill_model_capabilities(conn)
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (2, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
    logger.info("Database ready: %s", db_path)


def _apply_safe_migrations(conn: sqlite3.Connection) -> None:
    """幂等加列迁移：旧库补列，已存在则静默跳过（见 DEVELOPMENT_PITFALLS.md）。"""
    statements = [
        "ALTER TABLE novels ADD COLUMN deleted_at TEXT",
        "ALTER TABLE chapters ADD COLUMN deleted_at TEXT",
        "ALTER TABLE models ADD COLUMN capabilities TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE models ADD COLUMN capability_source TEXT NOT NULL DEFAULT 'auto'",
    ]
    for statement in statements:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass


def _backfill_model_capabilities(conn: sqlite3.Connection) -> None:
    """刷新全部自动推断模型的能力（内置目录优先；手动覆盖的不动）。"""
    from app.services.capability_registry import resolve_default_capabilities, serialize

    rows = conn.execute(
        """
        SELECT m.id, m.model_id, m.model_type, p.preset_key
        FROM models m
        JOIN providers p ON p.id = m.provider_id
        WHERE m.capability_source = 'auto'
        """
    ).fetchall()
    for row in rows:
        caps = resolve_default_capabilities(
            row["preset_key"], row["model_id"], row["model_type"]
        )
        conn.execute(
            "UPDATE models SET capabilities = ? WHERE id = ?",
            (serialize(caps), row["id"]),
        )
    if rows:
        logger.info("Refreshed capabilities for %d auto model(s)", len(rows))
