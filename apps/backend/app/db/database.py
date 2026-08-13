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
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (1, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
    logger.info("Database ready: %s", db_path)
