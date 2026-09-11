"""Episode pipeline scope, immutable run snapshots, and isolated stage state."""

import uuid
from types import SimpleNamespace

import pytest

from app.core.errors import AppError
from app.db.database import get_connection, init_db
from app.schemas.workflow_template import WorkflowConfig
from app.services.job_store import JOB_TYPE_GENERATION, JobStore
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
