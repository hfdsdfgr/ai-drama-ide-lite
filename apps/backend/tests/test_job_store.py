"""Phase 10 — JobStore 单元测试（持久化、状态机、幂等、stale 恢复、旧库迁移）。"""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.job_store import (
    CATEGORY_RETRYABLE,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    STATUS_PAUSED,
    STATUS_QUEUED,
    STATUS_RUNNING,
    JobStore,
)


@pytest.fixture()
def store(tmp_path: Path) -> JobStore:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    return JobStore(db_path)


def _create_job(store: JobStore, project_id: str = "proj_1", **kwargs):
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with get_connection(store.db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO projects
                (id, name, description, created_at, updated_at)
            VALUES (?, ?, '', ?, ?)
            """,
            (project_id, project_id, now, now),
        )
    defaults = {
        "model_id": "model_x",
        "provider_id": "prov_1",
        "capability": "text_to_image",
        "input_payload": {"prompt": "test"},
    }
    defaults.update(kwargs)
    return store.create("generation", project_id, **defaults)


def test_create_and_get(store):
    job = _create_job(store)
    assert job.id.startswith("job_")
    assert job.status == STATUS_QUEUED
    assert job.model_id == "model_x"
    assert job.provider_id == "prov_1"
    assert job.capability == "text_to_image"
    assert job.input_payload == {"prompt": "test"}
    assert job.progress == 0
    assert job.attempts == 0
    assert job.created_at


def test_create_json_roundtrip(store):
    job = _create_job(store, input_payload={"中文": "值", "nested": {"a": [1, 2]}})
    assert store.get(job.id).input_payload == {
        "中文": "值",
        "nested": {"a": [1, 2]},
    }


def test_get_missing_raises(store):
    with pytest.raises(AppError) as exc:
        store.get("job_missing")
    assert exc.value.status_code == 404


def test_list_filters(store):
    job_a = _create_job(store, project_id="proj_1")
    job_b = _create_job(store, project_id="proj_2")
    store.cancel(job_b.id)

    assert [j.id for j in store.list_jobs()] == [job_b.id, job_a.id]
    assert [j.id for j in store.list_jobs(project_id="proj_1")] == [job_a.id]
    assert [j.id for j in store.list_jobs(status=STATUS_CANCELLED)] == [job_b.id]
    assert [j.id for j in store.list_jobs(limit=1)] == [job_b.id]


def test_lifecycle_completed(store):
    job = _create_job(store)
    assert store.mark_running(job.id) is True
    running = store.get(job.id)
    assert running.status == STATUS_RUNNING
    assert running.attempts == 1
    assert running.started_at

    assert (
        store.mark_completed(
            job.id,
            result_payload={"urls": ["/a.png"]},
            output_files=["a.png"],
        )
        is True
    )
    done = store.get(job.id)
    assert done.status == STATUS_COMPLETED
    assert done.progress == 100
    assert done.result_payload == {"urls": ["/a.png"]}
    assert done.output_files == ["a.png"]
    assert done.completed_at
    # 幂等：重复 completed 不覆盖
    assert store.mark_completed(job.id) is False


def test_mark_failed(store):
    job = _create_job(store)
    store.mark_running(job.id)
    assert store.mark_failed(job.id, "boom", CATEGORY_RETRYABLE) is True
    failed = store.get(job.id)
    assert failed.status == STATUS_FAILED
    assert failed.error == "boom"
    assert failed.error_category == CATEGORY_RETRYABLE
    # 幂等：重复 failed 不覆盖
    assert store.mark_failed(job.id, "again") is False


def test_cancel_idempotent(store):
    job = _create_job(store)
    cancelled = store.cancel(job.id)
    assert cancelled.status == STATUS_CANCELLED
    assert cancelled.cancelled_at

    again = store.cancel(job.id)
    assert again.status == STATUS_CANCELLED
    assert again.cancelled_at == cancelled.cancelled_at
    # 已取消不能再次进入 running
    assert store.mark_running(job.id) is False


def test_cancel_running(store):
    job = _create_job(store)
    store.mark_running(job.id)
    assert store.cancel(job.id).status == STATUS_CANCELLED


def test_mark_running_only_from_queued(store):
    job = _create_job(store)
    assert store.mark_running(job.id) is True
    assert store.mark_running(job.id) is False


def test_pause_resume(store):
    job = _create_job(store)
    # 非 running 不能暂停，保持原状态
    assert store.pause(job.id).status == STATUS_QUEUED
    store.mark_running(job.id)
    assert store.pause(job.id).status == STATUS_PAUSED
    assert store.get(job.id).paused_at
    assert store.resume(job.id).status == STATUS_QUEUED


def test_progress_clamped_and_heartbeat(store):
    job = _create_job(store)
    store.mark_running(job.id)
    store.update_progress(job.id, 150)
    assert store.get(job.id).progress == 100
    store.update_progress(job.id, -5)
    assert store.get(job.id).progress == 0
    assert store.get(job.id).heartbeat_at


def test_recover_stale(store):
    job_stale = _create_job(store)
    store.mark_running(job_stale.id)
    with get_connection(store.db_path) as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at = '2020-01-01T00:00:00Z' WHERE id = ?",
            (job_stale.id,),
        )

    job_fresh = _create_job(store)
    store.mark_running(job_fresh.id)

    job_paused = _create_job(store)
    store.mark_running(job_paused.id)
    store.pause(job_paused.id)

    assert store.recover_stale(stale_after_s=60) == 1
    assert store.get(job_stale.id).status == STATUS_QUEUED
    assert store.get(job_stale.id).error_category == CATEGORY_RETRYABLE
    assert store.get(job_fresh.id).status == STATUS_RUNNING
    assert store.get(job_paused.id).status == STATUS_PAUSED


def test_persistence_across_instances(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = JobStore(db_path)
    job = _create_job(store)
    store.mark_running(job.id)
    store.mark_completed(job.id, result_payload={"ok": True})

    # 新实例（模拟应用重启）
    store2 = JobStore(db_path)
    restored = store2.get(job.id)
    assert restored.status == STATUS_COMPLETED
    assert restored.result_payload == {"ok": True}


def test_legacy_jobs_table_migrated(tmp_path: Path):
    """旧版 jobs 表（Phase 1 占位结构）经 init_db 补齐 Phase 10 新列。"""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.executescript(
        """
        CREATE TABLE projects (
            id TEXT PRIMARY KEY, name TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL, deleted_at TEXT
        );
        CREATE TABLE jobs (
            id TEXT PRIMARY KEY,
            project_id TEXT NOT NULL,
            type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'Queued',
            progress INTEGER NOT NULL DEFAULT 0,
            input TEXT NOT NULL DEFAULT '',
            output TEXT NOT NULL DEFAULT '',
            error TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            started_at TEXT,
            completed_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()

    init_db(db_path)
    with get_connection(db_path) as migrated:
        cols = {
            row["name"]
            for row in migrated.execute("PRAGMA table_info(jobs)").fetchall()
        }
    for expected in [
        "model_id",
        "provider_id",
        "capability",
        "task_id",
        "input_payload",
        "result_payload",
        "output_files",
        "error_category",
        "attempts",
        "max_attempts",
        "heartbeat_at",
        "paused_at",
        "cancelled_at",
    ]:
        assert expected in cols
