"""Phase 10 — JobWorker 单元测试（调度、失败分类、轮询、取消）。"""

import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.services.adapters.base import GenerationResult, JobStatus
from app.services.job_store import (
    CATEGORY_PERMANENT,
    CATEGORY_RETRYABLE,
    STATUS_CANCELLED,
    STATUS_COMPLETED,
    STATUS_FAILED,
    JobStore,
)
from app.services.job_worker import JobWorker, classify_error


class _FakeAdapter:
    def __init__(self, poll_states=None, poll_error=None):
        self.poll_states = list(poll_states or [])
        self.poll_error = poll_error
        self.poll_calls = 0

    def poll(self, ctx, task_id):
        self.poll_calls += 1
        if self.poll_error:
            raise self.poll_error
        if self.poll_states:
            return self.poll_states.pop(0)
        return JobStatus(job_id=task_id, status="running")


class _FakeManager:
    def __init__(self, mode="sync", result=None, submit_error=None, adapter=None):
        self.mode = mode
        self.result = result
        self.submit_error = submit_error
        self.adapter = adapter or _FakeAdapter()
        self.start_calls = []

    def start_job(self, model_id, capability, request):
        self.start_calls.append((model_id, capability, request))
        if self.submit_error:
            raise self.submit_error
        if self.mode == "sync":
            return {"mode": "sync", "result": self.result}
        return {"mode": "async", "task_id": "task-1", "result": None}

    def adapter_for(self, model_id, capability):
        return self.adapter

    def ctx_for(self, model_id):
        return object()


def _init(tmp_path: Path):
    db_path = tmp_path / "test.db"
    init_db(db_path)
    store = JobStore(db_path)
    now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    with get_connection(db_path) as conn:
        conn.execute(
            """
            INSERT OR IGNORE INTO projects
                (id, name, description, created_at, updated_at)
            VALUES ('proj_1', 'p', '', ?, ?)
            """,
            (now, now),
        )
    return store


def _make_job(store: JobStore, job_type="generation", **kwargs):
    defaults = {
        "model_id": "model_x",
        "provider_id": "prov_1",
        "capability": "text_to_image",
        "input_payload": {"prompt": "x"},
    }
    defaults.update(kwargs)
    return store.create(job_type, "proj_1", **defaults)


def _worker(store, manager, tmp_path: Path, **kwargs):
    return JobWorker(store, manager, tmp_path / "out", **kwargs)


def test_classify_error():
    assert classify_error(AppError(429, "rate", "x")) == CATEGORY_RETRYABLE
    assert classify_error(AppError(500, "e", "x")) == CATEGORY_RETRYABLE
    assert classify_error(AppError(504, "t", "x")) == CATEGORY_RETRYABLE
    assert classify_error(AppError(401, "key", "x")) == CATEGORY_PERMANENT
    assert classify_error(AppError(422, "cap", "x")) == CATEGORY_PERMANENT
    assert classify_error(ValueError("boom")) == CATEGORY_RETRYABLE


def test_sync_generation_completed(tmp_path):
    store = _init(tmp_path)
    out = tmp_path / "out"
    local_file = out / "a.png"
    manager = _FakeManager(
        mode="sync",
        result=GenerationResult(
            urls=[str(local_file)], meta={"n": 1}
        ),
    )
    worker = _worker(store, manager, tmp_path)
    job = _make_job(store)

    worker._execute(job)

    done = store.get(job.id)
    assert done.status == STATUS_COMPLETED
    assert done.progress == 100
    assert done.result_payload == {"urls": [str(local_file)], "meta": {"n": 1}}
    assert done.output_files == [str(local_file)]


def test_sync_generation_permanent_failure(tmp_path):
    store = _init(tmp_path)
    manager = _FakeManager(
        mode="sync",
        submit_error=AppError(401, "api_key_invalid", "API Key 无效"),
    )
    worker = _worker(store, manager, tmp_path)
    job = _make_job(store)

    worker._execute(job)

    failed = store.get(job.id)
    assert failed.status == STATUS_FAILED
    assert failed.error == "API Key 无效"
    assert failed.error_category == CATEGORY_PERMANENT


def test_async_generation_polls_to_completed(tmp_path):
    store = _init(tmp_path)
    adapter = _FakeAdapter(
        poll_states=[
            JobStatus(job_id="task-1", status="running"),
            JobStatus(
                job_id="task-1",
                status="completed",
                result=GenerationResult(urls=["https://cdn/v.mp4"]),
            ),
        ]
    )
    manager = _FakeManager(mode="async", adapter=adapter)
    worker = _worker(store, manager, tmp_path, poll_interval=0.01)
    job = _make_job(store, capability="text_to_video")

    worker._execute(job)

    done = store.get(job.id)
    assert done.status == STATUS_COMPLETED
    assert done.result_payload["urls"] == ["https://cdn/v.mp4"]
    assert done.task_id == "task-1"
    assert adapter.poll_calls == 2


def test_async_generation_vendor_failed(tmp_path):
    store = _init(tmp_path)
    adapter = _FakeAdapter(
        poll_states=[
            JobStatus(job_id="task-1", status="failed", error="视频生成失败")
        ]
    )
    manager = _FakeManager(mode="async", adapter=adapter)
    worker = _worker(store, manager, tmp_path, poll_interval=0.01)
    job = _make_job(store, capability="text_to_video")

    worker._execute(job)

    failed = store.get(job.id)
    assert failed.status == STATUS_FAILED
    assert failed.error == "视频生成失败"
    assert failed.error_category == CATEGORY_RETRYABLE


def test_async_poll_error_classified(tmp_path):
    store = _init(tmp_path)
    adapter = _FakeAdapter(poll_error=AppError(401, "api_key_invalid", "Key 无效"))
    manager = _FakeManager(mode="async", adapter=adapter)
    worker = _worker(store, manager, tmp_path, poll_interval=0.01)
    job = _make_job(store)

    worker._execute(job)

    failed = store.get(job.id)
    assert failed.status == STATUS_FAILED
    assert failed.error_category == CATEGORY_PERMANENT


def test_cancel_stops_polling(tmp_path):
    store = _init(tmp_path)
    adapter = _FakeAdapter(
        poll_states=[JobStatus(job_id="task-1", status="running")] * 20
    )
    manager = _FakeManager(mode="async", adapter=adapter)
    worker = _worker(store, manager, tmp_path, poll_interval=0.02)
    job = _make_job(store)

    thread = threading.Thread(target=worker._execute, args=(job,))
    thread.start()
    deadline = time.time() + 3
    while adapter.poll_calls < 1 and time.time() < deadline:
        time.sleep(0.01)

    store.cancel(job.id)
    thread.join(timeout=3)
    assert not thread.is_alive()
    assert store.get(job.id).status == STATUS_CANCELLED

    calls_after_cancel = adapter.poll_calls
    time.sleep(0.1)
    assert adapter.poll_calls == calls_after_cancel


def test_unknown_job_type_fails(tmp_path):
    store = _init(tmp_path)
    manager = _FakeManager()
    worker = _worker(store, manager, tmp_path)
    job = _make_job(store, job_type="weird")

    worker._execute(job)

    failed = store.get(job.id)
    assert failed.status == STATUS_FAILED
    assert "未知任务类型" in failed.error
    assert failed.error_category == CATEGORY_PERMANENT


def test_worker_start_drains_queued(tmp_path):
    store = _init(tmp_path)
    out = tmp_path / "out"
    local_file = out / "b.png"
    manager = _FakeManager(
        mode="sync", result=GenerationResult(urls=[str(local_file)])
    )
    worker = _worker(store, manager, tmp_path, scan_interval=0.02, poll_interval=0.01)
    job = _make_job(store)

    worker.start()
    try:
        deadline = time.time() + 3
        while store.get(job.id).status != STATUS_COMPLETED and time.time() < deadline:
            time.sleep(0.02)
        assert store.get(job.id).status == STATUS_COMPLETED
        assert manager.start_calls
    finally:
        worker.stop()


def test_worker_start_recovers_stale(tmp_path):
    store = _init(tmp_path)
    out = tmp_path / "out"
    manager = _FakeManager(
        mode="sync", result=GenerationResult(urls=[str(out / "c.png")])
    )
    job = _make_job(store)
    store.mark_running(job.id)
    with get_connection(store.db_path) as conn:
        conn.execute(
            "UPDATE jobs SET heartbeat_at = '2020-01-01T00:00:00Z' WHERE id = ?",
            (job.id,),
        )

    worker = _worker(store, manager, tmp_path, scan_interval=0.02, poll_interval=0.01)
    worker.start()
    try:
        deadline = time.time() + 3
        while store.get(job.id).status != STATUS_COMPLETED and time.time() < deadline:
            time.sleep(0.02)
        assert store.get(job.id).status == STATUS_COMPLETED
    finally:
        worker.stop()
