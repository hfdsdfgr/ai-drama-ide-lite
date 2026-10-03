"""Episode pipeline scope, immutable run snapshots, and isolated stage state."""

import uuid
import threading
from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.schemas.workflow_template import WorkflowConfig
from app.services.job_store import JOB_TYPE_GENERATION, JobStore
from app.services.job_worker import JobWorker
from app.services.adapters.base import GenerationResult, JobStatus
from app.services.pipeline_service import PipelineService
from app.services.workflow_template_service import WorkflowTemplateService


class _Repo:
    def __init__(self):
        self.models = {
            "llm_a": SimpleNamespace(id="llm_a", model_id="llm-a", model_type="llm", capabilities=[]),
            "image_a": SimpleNamespace(id="image_a", model_id="image-a", model_type="image", capabilities=["text_to_image"]),
            "image_b": SimpleNamespace(id="image_b", model_id="image-b", model_type="image", capabilities=["text_to_image"]),
            "video_a": SimpleNamespace(id="video_a", model_id="video-a", model_type="video", capabilities=["image_to_video"]),
            "video_b": SimpleNamespace(id="video_b", model_id="video-b", model_type="video", capabilities=["image_to_video"]),
        }

    def list_models(self, model_type=None, enabled_only=True):
        return [model for model in self.models.values() if model.model_type == model_type]


class _GenerationFakes:
    def __init__(self, db_path, store):
        self.db_path = db_path
        self.store = store
        self.image_calls = []
        self.video_calls = []

    def start_shot(self, project_id, shot_id, model_id, **kwargs):
        self.image_calls.append((project_id, shot_id, model_id, kwargs))
        self._version(project_id, "shot", shot_id, model_id)
        return self._completed_job(project_id, model_id, "text_to_image")

    def start_shot_video(self, project_id, shot_id, model_id, prompt, **kwargs):
        self.video_calls.append((project_id, shot_id, model_id, prompt, kwargs))
        self._version(project_id, "shot_video", shot_id, model_id)
        return self._completed_job(project_id, model_id, "image_to_video")

    def _completed_job(self, project_id, model_id, capability):
        job = self.store.create(JOB_TYPE_GENERATION, project_id, model_id=model_id, capability=capability)
        self.store.mark_running(job.id)
        self.store.mark_completed(job.id)
        return {"job_id": job.id}

    def _version(self, project_id, entity_type, entity_id, model_id):
        now = "2026-09-11T00:00:00Z"
        with get_connection(self.db_path) as conn:
            conn.execute(
                "UPDATE versions SET is_current = 0 WHERE entity_type = ? AND entity_id = ?",
                (entity_type, entity_id),
            )
            conn.execute(
                """INSERT INTO versions
                   (id, project_id, entity_type, entity_id, version, payload, file_path,
                    model_id, provider_id, job_id, is_current, created_at)
                   VALUES (?, ?, ?, ?, 1, '{}', 'test.png', ?, '', '', 1, ?)""",
                (f"version_{uuid.uuid4().hex[:10]}", project_id, entity_type, entity_id, model_id, now),
            )


def _setup(tmp_path):
    db_path = tmp_path / "episode-pipeline.db"
    init_db(db_path)
    now = "2026-09-11T00:00:00Z"
    with get_connection(db_path) as conn:
        conn.execute("INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', '项目', '', ?, ?)", (now, now))
        for suffix in ("1", "2"):
            conn.execute("INSERT INTO episodes (id, project_id, title, created_at, updated_at) VALUES (?, 'p', ?, ?, ?)", (f"ep{suffix}", f"第{suffix}集", now, now))
            conn.execute("INSERT INTO scenes (id, project_id, episode_id, title, created_at, updated_at) VALUES (?, 'p', ?, ?, ?, ?)", (f"scene{suffix}", f"ep{suffix}", f"场景{suffix}", now, now))
            conn.execute(
                """INSERT INTO shots
                   (id, project_id, scene_id, shot_number, order_index, characters, action,
                    dialogue, duration, prompt, created_at, updated_at)
                   VALUES (?, 'p', ?, 1, 0, '', '推进', '', 8, '镜头推进', ?, ?)""",
                (f"shot{suffix}", f"scene{suffix}", now, now),
            )
    manager = SimpleNamespace(repo=_Repo())
    store = JobStore(db_path)
    generated = _GenerationFakes(db_path, store)
    templates = WorkflowTemplateService(db_path, manager)
    service = PipelineService(
        db_path,
        manager,
        story_service=SimpleNamespace(),
        ai_script_service=SimpleNamespace(),
        asset_service=SimpleNamespace(),
        image_generation_service=generated,
        video_generation_service=generated,
        asset_version_service=None,
        workflow_template_service=templates,
    )
    return db_path, service, templates, store, generated


def _config(image_model="image_a", video_model="video_a"):
    return WorkflowConfig.model_validate(
        {
            "auto_continue": False,
            "storyboard": {"enabled": False, "model_id": "llm_a", "capability": "llm"},
            "shot_images": {"enabled": True, "model_id": image_model, "capability": "text_to_image", "aspect_ratio": "9:16"},
            "videos": {"enabled": True, "model_id": video_model, "capability": "image_to_video", "aspect_ratio": "720P", "duration_mode": "fixed", "duration": 10},
        }
    )


def test_episode_pipeline_is_scoped_and_keeps_start_snapshot(tmp_path):
    _db, service, templates, store, generated = _setup(tmp_path)
    saved = templates.put_episode_config("p", "ep2", 0, _config())
    parent = service.start_episode(store, "p", "ep2", expected_config_revision=saved["revision"])
    with pytest.raises(AppError) as conflict:
        service.start_episode(store, "p", "ep2", expected_config_revision=saved["revision"])
    assert conflict.value.code == "pipeline_already_active"

    templates.put_episode_config("p", "ep2", saved["revision"], _config("image_b", "video_b"))
    assert store.mark_running(parent.id)
    assert service.run(store.get(parent.id), store) is False
    assert store.get(parent.id).status == "paused"
    assert [(call[1], call[2]) for call in generated.image_calls] == [("shot2", "image_a")]

    store.resume(parent.id)
    assert store.mark_running(parent.id)
    assert service.run(store.get(parent.id), store) is True
    assert [(call[1], call[2]) for call in generated.video_calls] == [("shot2", "video_a")]
    assert generated.video_calls[0][4]["duration"] == 10
    assert generated.video_calls[0][4]["aspect_ratio"] == "720P"
    assert generated.video_calls[0][4]["with_audio"] is False
    assert not any(call[1] == "shot1" for call in generated.image_calls + generated.video_calls)
    states = service.status_episode("p", "ep2", parent.id)["stages"]
    assert {row["stage_key"]: row["status"] for row in states} == {
        "storyboard": "disabled",
        "shot_images": "completed",
        "videos": "completed",
    }


def test_episode_plan_blocks_video_without_keyframes_when_image_stage_disabled(tmp_path):
    _db, service, templates, _store, _generated = _setup(tmp_path)
    config = _config()
    config.shot_images.enabled = False
    saved = templates.put_episode_config("p", "ep2", 0, config)
    plan = service.plan_episode("p", "ep2")
    video = next(stage for stage in plan["stages"] if stage["key"] == "videos")
    assert saved["revision"] == plan["config_revision"]
    assert video["status"] == "not_ready"
    assert "关键帧" in video["missing_reason"]
    assert plan["can_start"] is False


def _queued_worker(tmp_path, *, async_mode=False):
    db, service, templates, store, generated = _setup(tmp_path)
    submissions = []
    adapter = SimpleNamespace(on_poll=None)

    def submit(model_id, capability, request):
        submissions.append((model_id, capability))
        if async_mode:
            return {"mode": "async", "task_id": f"remote-{len(submissions)}"}
        return {"mode": "sync", "result": GenerationResult()}

    def poll(_ctx, task_id):
        if adapter.on_poll:
            action, adapter.on_poll = adapter.on_poll, None
            action()
            return JobStatus(task_id, "running")
        return JobStatus(task_id, "completed", result=GenerationResult())

    adapter.poll = poll
    manager = SimpleNamespace(
        repo=service.manager.repo, start_job=submit,
        adapter_for=lambda *_: adapter, ctx_for=lambda *_: object(),
    )

    def enqueue(project_id, shot_id, model_id, capability, entity_type):
        return {"job_id": store.create(
            JOB_TYPE_GENERATION, project_id, model_id=model_id, capability=capability,
            input_payload={"shot_id": shot_id, "entity_type": entity_type},
        ).id}

    generated.start_shot = lambda p, s, m, **_: enqueue(p, s, m, "text_to_image", "shot")
    generated.start_shot_video = lambda p, s, m, *_args, **_: enqueue(p, s, m, "image_to_video", "shot_video")
    result_service = SimpleNamespace(persist=lambda job, _result: generated._version(
        job.project_id, job.input_payload["entity_type"], job.input_payload["shot_id"], job.model_id,
    ))
    worker = JobWorker(
        store, manager, tmp_path / "out", poll_interval=0.001,
        pipeline_service=service, image_result_service=result_service,
    )
    service.execute_child = worker.execute_pipeline_child
    return db, service, templates, store, worker, submissions, adapter


def _drain_bounded(worker, parent):
    thread = threading.Thread(target=worker._drain, daemon=True)
    thread.start()
    thread.join(timeout=5)
    if thread.is_alive():
        worker.store.cancel_many([parent.id])
        worker.stop()
        thread.join(timeout=3)
        pytest.fail("Single-worker pipeline blocked waiting for its queued child")


@pytest.mark.parametrize("scope", ["episode", "project"])
def test_single_worker_executes_real_queued_pipeline_children(tmp_path, scope):
    _db, service, templates, store, worker, submissions, _adapter = _queued_worker(tmp_path)
    if scope == "episode":
        config = _config()
        config.auto_continue = True
        templates.put_episode_config("p", "ep2", 0, config)
        parent = service.start_episode(store, "p", "ep2", expected_config_revision=1)
    else:
        # Existing upstream stages are complete; exercise both queued media stages.
        from app.services.pipeline_service import PIPELINE_STAGES
        for stage in PIPELINE_STAGES:
            service._set_stage("p", stage["key"], "completed" if stage["key"] not in {"shot_images", "videos"} else "queued", "")
        parent = store.create("pipeline", "p", input_payload={
            "project_id": "p", "auto_continue": True, "include_videos": True,
        })
    _drain_bounded(worker, parent)
    assert store.get(parent.id).status == "completed"
    children = [job for job in store.list_jobs("p") if job.type == JOB_TYPE_GENERATION]
    assert len(children) == (2 if scope == "episode" else 4)
    assert all(job.status == "completed" and job.attempts == 1 for job in children)
    assert len(submissions) == len(children)


@pytest.mark.parametrize("scope", ["episode", "project"])
def test_pipeline_pause_resume_reuses_remote_child_without_resubmitting(tmp_path, scope):
    _db, service, templates, store, worker, submissions, adapter = _queued_worker(tmp_path, async_mode=True)
    if scope == "episode":
        config = _config()
        config.videos.enabled = False
        templates.put_episode_config("p", "ep2", 0, config)
        parent = service.start_episode(store, "p", "ep2", expected_config_revision=1)
    else:
        from app.services.pipeline_service import PIPELINE_STAGES
        for stage in PIPELINE_STAGES:
            service._set_stage("p", stage["key"], "completed" if stage["key"] != "shot_images" else "queued", "")
        parent = store.create("pipeline", "p", input_payload={"project_id": "p", "auto_continue": True})
    adapter.on_poll = lambda: store.pause(parent.id)
    _drain_bounded(worker, parent)
    assert store.get(parent.id).status == "paused"
    child = next(job for job in store.list_jobs("p") if job.type == JOB_TYPE_GENERATION)
    assert child.status == "paused"
    assert child.task_id == "remote-1"
    assert len(submissions) == 1

    # Project-wide resume may queue the newer child before its parent. The worker
    # must defer it to its parent and retain the original remote task ID.
    store.resume_many([child.id, parent.id])
    _drain_bounded(worker, parent)
    assert store.get(parent.id).status == "completed"
    assert store.get(child.id).task_id == "remote-1"
    assert store.get(child.id).status == "completed"
    assert len(submissions) == (1 if scope == "episode" else 2)


@pytest.mark.parametrize("action", ["cancel", "stop"])
def test_pipeline_interrupt_stops_child_polling(tmp_path, action):
    _db, service, templates, store, worker, submissions, adapter = _queued_worker(tmp_path, async_mode=True)
    config = _config()
    templates.put_episode_config("p", "ep2", 0, config)
    parent = service.start_episode(store, "p", "ep2", expected_config_revision=1)
    adapter.on_poll = (lambda: store.cancel(parent.id)) if action == "cancel" else worker.stop
    _drain_bounded(worker, parent)
    expected = "cancelled" if action == "cancel" else "paused"
    assert store.get(parent.id).status == expected
    child = next(job for job in store.list_jobs("p") if job.type == JOB_TYPE_GENERATION)
    assert child.status == expected
    assert child.task_id == "remote-1"
    assert len(submissions) == 1


def test_pipeline_child_failure_fails_parent_without_automatic_retry(tmp_path):
    _db, service, templates, store, worker, _submissions, _adapter = _queued_worker(tmp_path)
    config = _config()
    templates.put_episode_config("p", "ep2", 0, config)
    parent = service.start_episode(store, "p", "ep2", expected_config_revision=1)

    def fail(*_args):
        raise AppError(401, "invalid_key", "测试凭据无效")

    worker.manager.start_job = fail
    _drain_bounded(worker, parent)
    assert store.get(parent.id).status == "failed"
    children = [job for job in store.list_jobs("p") if job.type == JOB_TYPE_GENERATION]
    assert len(children) == 1
    assert children[0].status == "failed"
    assert children[0].attempts == 1
    assert children[0].error_category == "permanent"
