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
        conn.execute(
            "INSERT OR IGNORE INTO schema_migrations (version, applied_at) VALUES (3, ?)",
            (datetime.now(timezone.utc).isoformat(),),
        )
    logger.info("Database ready: %s", db_path)


def _apply_safe_migrations(conn: sqlite3.Connection) -> None:
    """幂等加列迁移：旧库补列，已存在则静默跳过（见 DEVELOPMENT_PITFALLS.md）。"""
    _migrate_jobs_table(conn)
    _migrate_models_audio_type(conn)
    statements = [
        "ALTER TABLE novels ADD COLUMN deleted_at TEXT",
        "ALTER TABLE novels ADD COLUMN ai_brief TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE chapters ADD COLUMN deleted_at TEXT",
        "ALTER TABLE models ADD COLUMN capabilities TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE models ADD COLUMN capability_source TEXT NOT NULL DEFAULT 'auto'",
        "ALTER TABLE providers ADD COLUMN protocol TEXT NOT NULL DEFAULT 'openai_compat'",
        "ALTER TABLE episodes ADD COLUMN novel_id TEXT REFERENCES novels(id) ON DELETE SET NULL",
        "ALTER TABLE episodes ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE episodes ADD COLUMN source_chapter_index INTEGER",
        "ALTER TABLE scenes ADD COLUMN novel_id TEXT REFERENCES novels(id) ON DELETE SET NULL",
        "ALTER TABLE scenes ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE scenes ADD COLUMN slugline TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE scenes ADD COLUMN action TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE scenes ADD COLUMN dialogue TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN order_index INTEGER NOT NULL DEFAULT 0",
        "ALTER TABLE shots ADD COLUMN shot_type TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN camera TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN characters TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN action TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN lighting TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN dialogue TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE shots ADD COLUMN duration REAL NOT NULL DEFAULT 0",
        "ALTER TABLE shots ADD COLUMN prompt TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE episodes ADD COLUMN deleted_at TEXT",
        "ALTER TABLE scenes ADD COLUMN deleted_at TEXT",
        "ALTER TABLE shots ADD COLUMN deleted_at TEXT",
        # Phase 9 — 资产版本系统：versions 表补齐新列
        "ALTER TABLE versions ADD COLUMN file_path TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE versions ADD COLUMN model_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE versions ADD COLUMN provider_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE versions ADD COLUMN job_id TEXT NOT NULL DEFAULT ''",
        "ALTER TABLE versions ADD COLUMN is_current INTEGER NOT NULL DEFAULT 0",
    ]
    for statement in statements:
        try:
            conn.execute(statement)
        except sqlite3.OperationalError:
            pass
    # 旧 Provider 按预设回填协议；自定义 Provider 保持 openai_compat。
    from app.services.vendor_presets import PRESETS

    for preset_key, preset in PRESETS.items():
        conn.execute(
            "UPDATE providers SET protocol = ? WHERE preset_key = ? AND protocol = 'openai_compat'",
            (preset.protocol, preset_key),
        )
    # 依赖新列的索引必须在加列之后创建（见 Phase 9 迁移顺序坑）
    try:
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_versions_entity_version
            ON versions(entity_type, entity_id, version)
            """
        )
        conn.execute(
            """
            CREATE UNIQUE INDEX IF NOT EXISTS idx_versions_current
            ON versions(entity_type, entity_id)
            WHERE is_current = 1
            """
        )
    except sqlite3.OperationalError:
        pass


def _migrate_jobs_table(conn: sqlite3.Connection) -> None:
    """旧版 jobs 表（Phase 1 占位结构）重建为 Phase 10 结构。

    差异：project_id 改为可空（生成测试任务不绑定项目）、补齐 model/provider/
    capability/payload/重试/心跳等新列。保留旧数据（占位表通常为空）。
    """
    cols = {
        row["name"]: row
        for row in conn.execute("PRAGMA table_info(jobs)").fetchall()
    }
    if (
        "model_id" in cols
        and "cancelled_at" in cols
        and not cols["project_id"]["notnull"]
    ):
        return  # 已是最新结构
    conn.execute("ALTER TABLE jobs RENAME TO jobs_old")
    conn.executescript(
        """
        CREATE TABLE jobs (
            id             TEXT PRIMARY KEY,
            project_id     TEXT REFERENCES projects(id) ON DELETE CASCADE,
            type           TEXT NOT NULL,
            status         TEXT NOT NULL DEFAULT 'queued',
            progress       INTEGER NOT NULL DEFAULT 0,
            model_id       TEXT NOT NULL DEFAULT '',
            provider_id    TEXT NOT NULL DEFAULT '',
            capability     TEXT NOT NULL DEFAULT '',
            task_id        TEXT NOT NULL DEFAULT '',
            input_payload  TEXT NOT NULL DEFAULT '{}',
            result_payload TEXT NOT NULL DEFAULT '{}',
            output_files   TEXT NOT NULL DEFAULT '[]',
            error          TEXT NOT NULL DEFAULT '',
            error_category TEXT NOT NULL DEFAULT '',
            attempts       INTEGER NOT NULL DEFAULT 0,
            max_attempts   INTEGER NOT NULL DEFAULT 1,
            created_at     TEXT NOT NULL,
            started_at     TEXT,
            completed_at   TEXT,
            heartbeat_at   TEXT,
            paused_at      TEXT,
            cancelled_at   TEXT
        );
        """
    )
    conn.execute(
        """
        INSERT INTO jobs (
            id, project_id, type, status, progress,
            model_id, provider_id, capability, task_id,
            input_payload, result_payload, output_files,
            error, error_category, attempts, max_attempts,
            created_at, started_at, completed_at, heartbeat_at, paused_at, cancelled_at
        )
        SELECT id, project_id, type, status, progress,
               '', '', '', '',
               '{}', '{}', '[]',
               error, '', 0, 1,
               created_at, started_at, completed_at, NULL, NULL, NULL
        FROM jobs_old
        """
    )
    conn.execute("DROP TABLE jobs_old")


def _migrate_models_audio_type(conn: sqlite3.Connection) -> None:
    """把 models.model_type 的 CHECK 约束扩展为支持 audio（旧库需重建表）。"""
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = 'models'"
    ).fetchone()
    if row and "audio" in (row["sql"] or ""):
        return
    conn.execute("DROP INDEX IF EXISTS idx_models_provider")
    conn.execute("DROP INDEX IF EXISTS idx_models_type")
    conn.execute("ALTER TABLE models RENAME TO models_old")
    conn.executescript(
        """
        CREATE TABLE models (
            id               TEXT PRIMARY KEY,
            provider_id      TEXT NOT NULL REFERENCES providers(id) ON DELETE CASCADE,
            model_id         TEXT NOT NULL,
            model_type       TEXT NOT NULL DEFAULT 'llm' CHECK (model_type IN ('llm', 'image', 'video', 'audio')),
            capabilities     TEXT NOT NULL DEFAULT '',
            capability_source TEXT NOT NULL DEFAULT 'auto',
            enabled          INTEGER NOT NULL DEFAULT 1,
            is_default_image INTEGER NOT NULL DEFAULT 0,
            is_default_video INTEGER NOT NULL DEFAULT 0,
            created_at       TEXT NOT NULL,
            updated_at       TEXT NOT NULL,
            deleted_at       TEXT,
            UNIQUE (provider_id, model_id)
        );
        """
    )
    conn.execute(
        """
        INSERT INTO models (
            id, provider_id, model_id, model_type, capabilities,
            capability_source, enabled, is_default_image, is_default_video,
            created_at, updated_at, deleted_at
        )
        SELECT id, provider_id, model_id, model_type, capabilities,
               capability_source, enabled, is_default_image, is_default_video,
               created_at, updated_at, deleted_at
        FROM models_old
        """
    )
    conn.execute("DROP TABLE models_old")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_models_provider ON models(provider_id)")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_models_type ON models(model_type)")


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
