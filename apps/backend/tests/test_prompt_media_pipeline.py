"""Custom creative rules reach media jobs and remain fixed across pipeline resumes."""

from types import SimpleNamespace

from app.services.image_generation_service import ImageGenerationService
from app.services.image_prompt_builder import build_asset_image_prompt, build_shot_image_prompt
from app.services.prompt_settings import PromptSettingsService
from app.services.script_repo import ScriptRepository
from app.services.story_repo import StoryRepository
from app.services.video_generation_service import VideoGenerationService
from tests.test_episode_pipeline_service import _config, _setup
from tests.test_image_generation_service import (
    _FakeAssetVersionService, _FakeGenerationService, _FakeProviderManager, _scene, _shot,
)


def _save(client, project_id, stage_id, rules, revision=0, **fields):
    response = client.put(
        f"/api/projects/{project_id}/prompt-settings/{stage_id}",
        json={"expected_revision": revision, "rules": rules, **fields},
    )
    assert response.status_code == 200, response.text
    return response.json()["revision"]


def test_media_builder_replaces_rules_without_mutating_reference_content():
    plan = build_asset_image_prompt(
        "character", "full body, front view, green robe",
        creative_rules="single portrait, pencil sketch", creative_negative_prompt="",
    )
    assert "single portrait, pencil sketch" in plan.prompt
    assert "full body, front view, green robe" in plan.prompt
    assert "three views" not in plan.prompt
    assert "solo character" not in plan.prompt
    assert plan.negative_prompt == ""
    shot = _shot(prompt="双人对峙")
    plan = build_shot_image_prompt(
        shot, _scene(),
        asset_references=[{"asset_type": "character", "name": "林凡", "reference_prompt": "green robe"}],
        creative_rules="", creative_negative_prompt="",
    )
    assert "green robe" in plan.prompt
    assert "cinematic still frame" not in plan.prompt
    assert "exact same face" not in plan.prompt
    assert plan.negative_prompt == ""
    assert shot.prompt == "双人对峙"


def test_project_image_rules_and_empty_negatives_reach_job(client, monkeypatch):
    project_id = client.post("/api/projects", json={"name": "custom media"}).json()["id"]
    _save(client, project_id, "image_character", "single portrait, pencil sketch", negative_prompt="")
    fake = _FakeGenerationService()
    service = ImageGenerationService(
        fake, _FakeProviderManager(), client.app.state.settings.db_path, _FakeAssetVersionService(),
    )
    monkeypatch.setattr(StoryRepository, "list_assets", lambda self, project: [{
        "asset_type": "character", "asset_id": "char1", "name": "林凡",
        "reference_prompt": "green robe", "fields": {},
    }])
    service.start_asset(project_id, "char1", "image1")
    args, kwargs = fake.calls[0]
    assert "single portrait, pencil sketch" in args[2]
    assert "three views" not in args[2]
    assert kwargs["negative_prompt"] == ""
    assert kwargs["extra"]["prompt_snapshot"]["revision"] == 1


def test_video_rules_replace_default_and_preserve_dialogue(client, monkeypatch):
    project_id = client.post("/api/projects", json={"name": "custom video"}).json()["id"]
    _save(client, project_id, "video_shot", "固定机位，轻微呼吸动作")
    fake = _FakeGenerationService()
    fake.manager = SimpleNamespace(repo=SimpleNamespace(
        get_model=lambda _: SimpleNamespace(capabilities=["video_dialogue"]),
    ))
    monkeypatch.setattr(ScriptRepository, "get_shot_with_scene", lambda *args: (
        _shot(dialogue="林凡：别走！"), _scene(),
    ))
    service = VideoGenerationService(fake, client.app.state.settings.db_path, _FakeAssetVersionService())
    service.start_shot_video(project_id, "shot1", "video1", "风吹衣摆", with_audio=True)
    args, kwargs = fake.calls[0]
    assert "风吹衣摆" in args[2]
    assert "固定机位，轻微呼吸动作" in args[2]
    assert "真实重力" not in args[2]
    assert "对白：林凡：别走！" in args[2]
    assert kwargs["extra"]["user_prompt"] == "风吹衣摆"


def test_episode_resume_keeps_prompt_snapshot_after_settings_change(tmp_path):
    db, pipeline, templates, store, generated = _setup(tmp_path)
    prompts = PromptSettingsService(db)
    # The persistence API is exercised through HTTP above; create an override in the fixture DB.
    from app.db.database import get_connection
    import json
    with get_connection(db) as conn:
        conn.execute(
            "INSERT INTO project_prompt_settings (project_id, revision, overrides_json, updated_at) VALUES ('p', 1, ?, '2026-10-02T00:00:00Z')",
            (json.dumps({"video_shot": {"rules": "固定机位"}}),),
        )
    saved = templates.put_episode_config("p", "ep2", 0, _config())
    parent = pipeline.start_episode(store, "p", "ep2", expected_config_revision=saved["revision"])
    assert parent.input_payload["prompt_snapshot"]["stages"]["video_shot"]["rules"] == "固定机位"
    with get_connection(db) as conn:
        conn.execute("UPDATE project_prompt_settings SET revision = 2, overrides_json = ? WHERE project_id = 'p'", (
            json.dumps({"video_shot": {"rules": "快速跟拍"}}),
        ))
    store.mark_running(parent.id)
    assert pipeline.run(store.get(parent.id), store) is False
    store.resume(parent.id)
    store.mark_running(parent.id)
    assert pipeline.run(store.get(parent.id), store) is True
    snapshot = generated.video_calls[0][4]["prompt_snapshot"]
    assert snapshot["revision"] == 1
    assert snapshot["stages"]["video_shot"]["rules"] == "固定机位"
    assert prompts.snapshot("p")["stages"]["video_shot"]["rules"] == "快速跟拍"


def test_project_pipeline_resume_keeps_prompt_snapshot(tmp_path, monkeypatch):
    from tests.test_pipeline_service import _FakeManager, _FakeStore, _Model, _setup as setup_project

    db, pipeline, services = setup_project(tmp_path, _FakeManager({
        "llm": _Model("llm", "llm", []),
        "image": _Model("image", "image", ["text_to_image"]),
    }))
    prompts = PromptSettingsService(db)
    prompts.update("p", "script_episode", 0, "对白简洁，优先动作")
    store = _FakeStore()
    monkeypatch.setattr(store, "create", lambda job_type, project_id, **kwargs: SimpleNamespace(
        id="pipe_1", project_id=project_id, input_payload=kwargs["input_payload"],
    ))
    seen = []
    original_start = services.start
    original_script = services.generate_episode_script

    def start(*args, prompt_snapshot=None, **kwargs):
        seen.append(prompt_snapshot)
        return original_start(*args, prompt_snapshot=prompt_snapshot, **kwargs)

    def script(*args, prompt_snapshot=None, **kwargs):
        seen.append(prompt_snapshot)
        return original_script(*args, prompt_snapshot=prompt_snapshot, **kwargs)

    monkeypatch.setattr(services, "start", start)
    monkeypatch.setattr(services, "generate_episode_script", script)
    parent = pipeline.start(store, "p")
    assert pipeline.run(parent, store) is False
    prompts.update("p", "script_episode", 1, "大量内心独白")
    assert pipeline.run(parent, store) is False
    assert len(seen) == 2
    assert all(snapshot["revision"] == 1 for snapshot in seen)
    assert seen[1]["stages"]["script_episode"]["rules"] == "对白简洁，优先动作"
    assert prompts.snapshot("p")["revision"] == 2


def test_invalid_prompt_settings_do_not_reset_existing_pipeline(tmp_path):
    import pytest

    from app.core.errors import AppError
    from app.db.database import get_connection
    from tests.test_pipeline_service import _FakeManager, _FakeStore, _Model, _setup as setup_project

    db, pipeline, _services = setup_project(tmp_path, _FakeManager({
        "llm": _Model("llm", "llm", []),
        "image": _Model("image", "image", ["text_to_image"]),
    }))
    with get_connection(db) as conn:
        conn.execute(
            "INSERT INTO pipelines (project_id, stage_key, status, message, updated_at) VALUES ('p', 'script', 'completed', '', '2026-10-02')",
        )
        conn.execute(
            "INSERT INTO project_prompt_settings (project_id, revision, overrides_json, updated_at) VALUES ('p', 1, 'broken json', '2026-10-02')",
        )
    with pytest.raises(AppError) as error:
        pipeline.start(_FakeStore(), "p")
    assert error.value.code == "prompt_settings_corrupt"
    assert pipeline.status("p")["stages"][0]["status"] == "completed"
