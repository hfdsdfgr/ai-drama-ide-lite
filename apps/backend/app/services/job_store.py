"""Phase 10 — 持久化 Job 存储（SQLite）。

职责：Job 的 CRUD、状态机迁移、幂等取消、启动时 stale recovery。

状态机（小写枚举）：
    queued  -> running -> completed / failed / cancelled
    queued  -> cancelled
    running -> paused   -> queued（重新排队，由 worker 统一从 queued 领取）
    running -> cancelled

终态（completed / failed / cancelled）上的迁移保持幂等：重复取消不报错、不覆盖。
状态迁移全部用「条件 UPDATE + rowcount」保证原子性，避免并发重复领取。

产品约束：一个 Job 只绑定一个 Model / 一个 Provider（单模型生成，不做并行）。
"""

import json
import sqlite3
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from app.core.errors import AppError
from app.db.database import get_connection

STATUS_QUEUED = "queued"
STATUS_RUNNING = "running"
STATUS_PAUSED = "paused"
STATUS_COMPLETED = "completed"
STATUS_FAILED = "failed"
STATUS_CANCELLED = "cancelled"

TERMINAL_STATUSES = {STATUS_COMPLETED, STATUS_FAILED, STATUS_CANCELLED}

CATEGORY_NONE = ""
CATEGORY_RETRYABLE = "retryable"
CATEGORY_PERMANENT = "permanent"

JOB_TYPE_GENERATION = "generation"
JOB_TYPE_ASSET_COMPLETION = "asset_completion"
JOB_TYPE_AUDIO_SEPARATION = "audio_separation"
JOB_TYPE_DIALOGUE_PLANNING = "dialogue_planning"
JOB_TYPE_TTS_GENERATION = "tts_generation"
JOB_TYPE_AUDIO_MIXING = "audio_mixing"
JOB_TYPE_MEDIA_COMPOSE = "media_compose"
JOB_TYPE_LIP_SYNC = "lip_sync"
JOB_TYPE_VIDEO_COMPOSE = "video_compose"
JOB_TYPE_DIALOGUE_REVIEW = "dialogue_review"
JOB_TYPE_VISUAL_REVIEW = "visual_review"
JOB_TYPE_STORY_REVIEW = "story_review"


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_json(value: str | None, default):
    if not value:
        return default
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return default


@dataclass
class JobRecord:
    id: str
    project_id: str
    type: str
    status: str
    progress: int
    model_id: str
    provider_id: str
    capability: str
    task_id: str
    input_payload: dict
    result_payload: dict
    output_files: list
    error: str
    error_category: str
    attempts: int
    max_attempts: int
    created_at: str
    started_at: str | None
    completed_at: str | None
    heartbeat_at: str | None
    paused_at: str | None
    cancelled_at: str | None

    @property
    def is_terminal(self) -> bool:
        return self.status in TERMINAL_STATUSES


def _row_to_record(row: sqlite3.Row) -> JobRecord:
    return JobRecord(
        id=row["id"],
        project_id=row["project_id"],
        type=row["type"],
        status=row["status"],
        progress=row["progress"],
        model_id=row["model_id"],
        provider_id=row["provider_id"],
        capability=row["capability"],
        task_id=row["task_id"],
        input_payload=_parse_json(row["input_payload"], {}),
        result_payload=_parse_json(row["result_payload"], {}),
        output_files=_parse_json(row["output_files"], []),
        error=row["error"],
        error_category=row["error_category"],
        attempts=row["attempts"],
        max_attempts=row["max_attempts"],
        created_at=row["created_at"],
        started_at=row["started_at"],
        completed_at=row["completed_at"],
        heartbeat_at=row["heartbeat_at"],
        paused_at=row["paused_at"],
        cancelled_at=row["cancelled_at"],
    )


class JobStore:
    def __init__(self, db_path: Path) -> None:
        self.db_path = db_path

    # ---------- CRUD ----------

    def create(
        self,
        job_type: str,
        project_id: str,
        *,
        model_id: str = "",
        provider_id: str = "",
        capability: str = "",
        input_payload: dict | None = None,
        max_attempts: int = 1,
    ) -> JobRecord:
        now = _now_iso()
        job_id = _new_id("job")
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                INSERT INTO jobs (
                    id, project_id, type, status, progress,
                    model_id, provider_id, capability,
                    input_payload, max_attempts, created_at
                ) VALUES (?, ?, ?, ?, 0, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id,
                    project_id,
                    job_type,
                    STATUS_QUEUED,
                    model_id,
                    provider_id,
                    capability,
                    json.dumps(input_payload or {}, ensure_ascii=False),
                    max_attempts,
                    now,
                ),
            )
        return self.get(job_id)

    def get(self, job_id: str) -> JobRecord:
        with get_connection(self.db_path) as conn:
            row = conn.execute(
                "SELECT * FROM jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise AppError(404, "job_not_found", f"任务不存在: {job_id}")
        return _row_to_record(row)

    def list_jobs(
        self,
        project_id: str | None = None,
        status: str | None = None,
        limit: int = 50,
    ) -> list[JobRecord]:
        clauses: list[str] = []
        params: list = []
        if project_id:
            clauses.append("project_id = ?")
            params.append(project_id)
        if status:
            clauses.append("status = ?")
            params.append(status)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        params.append(limit)
        with get_connection(self.db_path) as conn:
            rows = conn.execute(
                f"SELECT * FROM jobs {where} ORDER BY created_at DESC LIMIT ?",
                params,
            ).fetchall()
        return [_row_to_record(row) for row in rows]

    # ---------- 状态迁移（条件 UPDATE 保证原子性） ----------

    def mark_running(self, job_id: str) -> bool:
        """queued -> running；attempts +1。返回 False 表示状态不允许（已被领取/取消）。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = ?, heartbeat_at = ?, attempts = attempts + 1
                WHERE id = ? AND status = ?
                """,
                (STATUS_RUNNING, now, now, job_id, STATUS_QUEUED),
            )
            return cur.rowcount == 1

    def mark_completed(
        self,
        job_id: str,
        result_payload: dict | None = None,
        output_files: list | None = None,
    ) -> bool:
        """running -> completed。返回 False 表示状态不允许（幂等安全）。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?, progress = 100, result_payload = ?,
                    output_files = ?, completed_at = ?, heartbeat_at = ?
                WHERE id = ? AND status = ?
                """,
                (
                    STATUS_COMPLETED,
                    json.dumps(result_payload or {}, ensure_ascii=False),
                    json.dumps(output_files or [], ensure_ascii=False),
                    now,
                    now,
                    job_id,
                    STATUS_RUNNING,
                ),
            )
            return cur.rowcount == 1

    def mark_failed(
        self,
        job_id: str,
        error: str,
        category: str = CATEGORY_NONE,
    ) -> bool:
        """running -> failed。返回 False 表示状态不允许（幂等安全）。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?, error = ?, error_category = ?, completed_at = ?
                WHERE id = ? AND status = ?
                """,
                (STATUS_FAILED, error, category, now, job_id, STATUS_RUNNING),
            )
            return cur.rowcount == 1

    def cancel(self, job_id: str) -> JobRecord:
        """queued / running -> cancelled。终态重复取消幂等，返回当前记录。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, cancelled_at = ?, completed_at = ?
                WHERE id = ? AND status IN (?, ?)
                """,
                (STATUS_CANCELLED, now, now, job_id, STATUS_QUEUED, STATUS_RUNNING),
            )
        return self.get(job_id)

    def cancel_many(self, job_ids: list[str]) -> int:
        """批量取消 queued / running 任务，终态任务自动跳过，返回受影响数量。"""
        if not job_ids:
            return 0
        now = _now_iso()
        placeholders = ",".join("?" * len(job_ids))
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                f"""
                UPDATE jobs
                SET status = ?, cancelled_at = ?, completed_at = ?
                WHERE id IN ({placeholders}) AND status IN (?, ?, ?)
                """,
                (
                    STATUS_CANCELLED,
                    now,
                    now,
                    *job_ids,
                    STATUS_QUEUED,
                    STATUS_RUNNING,
                    STATUS_PAUSED,
                ),
            )
            return cur.rowcount

    def pause(self, job_id: str) -> JobRecord:
        """running -> paused。仅允许运行中的任务暂停。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs SET status = ?, paused_at = ?
                WHERE id = ? AND status = ?
                """,
                (STATUS_PAUSED, now, job_id, STATUS_RUNNING),
            )
        return self.get(job_id)

    def pause_many(self, job_ids: list[str]) -> int:
        """批量暂停 running 任务，返回受影响数量。"""
        if not job_ids:
            return 0
        now = _now_iso()
        placeholders = ",".join("?" * len(job_ids))
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                f"""
                UPDATE jobs SET status = ?, paused_at = ?
                WHERE id IN ({placeholders}) AND status = ?
                """,
                (STATUS_PAUSED, now, *job_ids, STATUS_RUNNING),
            )
            return cur.rowcount

    def resume(self, job_id: str) -> JobRecord:
        """paused -> queued（重新排队，worker 统一从 queued 领取）。"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, paused_at = NULL, started_at = NULL, heartbeat_at = NULL
                WHERE id = ? AND status = ?
                """,
                (STATUS_QUEUED, job_id, STATUS_PAUSED),
            )
        return self.get(job_id)

    def resume_many(self, job_ids: list[str]) -> int:
        """批量恢复 paused 任务为 queued，返回受影响数量。"""
        if not job_ids:
            return 0
        placeholders = ",".join("?" * len(job_ids))
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                f"""
                UPDATE jobs
                SET status = ?, paused_at = NULL, started_at = NULL, heartbeat_at = NULL
                WHERE id IN ({placeholders}) AND status = ?
                """,
                (STATUS_QUEUED, *job_ids, STATUS_PAUSED),
            )
            return cur.rowcount

    def retry(self, job_id: str) -> JobRecord:
        """failed / cancelled -> queued（用户手动重试），重置错误与尝试次数。

        默认不自动重试（防重复费用）；重试一律由用户显式触发。
        """
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs
                SET status = ?, attempts = 0, error = '', error_category = '',
                    progress = 0, task_id = '',
                    started_at = NULL, completed_at = NULL,
                    heartbeat_at = NULL, paused_at = NULL, cancelled_at = NULL
                WHERE id = ? AND status IN (?, ?)
                """,
                (STATUS_QUEUED, job_id, STATUS_FAILED, STATUS_CANCELLED),
            )
        return self.get(job_id)

    def update_progress(self, job_id: str, progress: int) -> None:
        """更新进度并刷新心跳（running 状态才允许；静默忽略其他状态）。"""
        now = _now_iso()
        with get_connection(self.db_path) as conn:
            conn.execute(
                """
                UPDATE jobs SET progress = ?, heartbeat_at = ?
                WHERE id = ? AND status = ?
                """,
                (max(0, min(progress, 100)), now, job_id, STATUS_RUNNING),
            )

    def set_task_id(self, job_id: str, task_id: str) -> None:
        """记录厂商异步任务 ID（轮询用）。"""
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE jobs SET task_id = ? WHERE id = ?",
                (task_id, job_id),
            )

    def recover_stale(self, stale_after_s: int = 300) -> int:
        """启动恢复：running 且心跳超时（进程崩溃残留）翻回 queued。

        返回恢复数量。paused 任务保持暂停（用户意图保留，可手动 resume）。
        """
        cutoff = (
            datetime.now(timezone.utc) - timedelta(seconds=stale_after_s)
        ).isoformat().replace("+00:00", "Z")
        with get_connection(self.db_path) as conn:
            cur = conn.execute(
                """
                UPDATE jobs
                SET status = ?, started_at = NULL, heartbeat_at = NULL,
                    error = ?, error_category = ?
                WHERE status = ? AND (heartbeat_at IS NULL OR heartbeat_at < ?)
                """,
                (
                    STATUS_QUEUED,
                    "任务在运行中中断，已恢复为排队状态，可手动重试",
                    CATEGORY_RETRYABLE,
                    STATUS_RUNNING,
                    cutoff,
                ),
            )
            return cur.rowcount
