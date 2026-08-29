"""Phase 14 M1 - Video generation API route tests."""

from types import SimpleNamespace

from app.db.database import get_connection


def _job_out(model_id="model_video", capability="image_to_video"):
    return {
        "job_id": "job_1",
        "model_id": model_id,
        "capability": capability,
        "status": "queued",
        "error": None,
        "result": None,
        "created_at": "2026-08-15T00:00:00Z",
    }


def test_generate_shot_video_route(client, monkeypatch):
    calls = {}

    def fake_start_shot_video(
        project_id,
        shot_id,
        model_id,
        prompt,
        *,
        duration=5,
        aspect_ratio=None,
        with_audio=False,
    ):
        calls.update(
            {
                "project_id": project_id,
                "shot_id": shot_id,
                "model_id": model_id,
                "prompt": prompt,
                "duration": duration,
                "with_audio": with_audio,
            }
        )
        return _job_out(model_id)

    monkeypatch.setattr(
        client.app.state.video_generation_service,
        "start_shot_video",
        fake_start_shot_video,
    )

    response = client.post(
        "/api/projects/proj_1/videos/generate",
        json={
            "target_id": "shot_01",
            "model_id": "model_video",
            "prompt": "镜头缓缓推进",
            "duration": 10,
        },
    )

    assert response.status_code == 201
    assert response.json()["capability"] == "image_to_video"
    assert calls["project_id"] == "proj_1"
    assert calls["shot_id"] == "shot_01"
    assert calls["duration"] == 10
    assert calls["with_audio"] is False


def test_generate_shot_video_route_passes_with_audio(client, monkeypatch):
    calls = {}

    def fake_start_shot_video(
        project_id,
        shot_id,
        model_id,
        prompt,
        *,
        duration=5,
        aspect_ratio=None,
        with_audio=False,
    ):
        calls["with_audio"] = with_audio
        return _job_out(model_id)

    monkeypatch.setattr(
        client.app.state.video_generation_service,
        "start_shot_video",
        fake_start_shot_video,
    )

    response = client.post(
        "/api/projects/proj_1/videos/generate",
        json={
            "target_id": "shot_01",
            "model_id": "model_video",
            "prompt": "镜头缓缓推进",
            "duration": 10,
            "with_audio": True,
        },
    )

    assert response.status_code == 201
    assert calls["with_audio"] is True


def test_video_generate_requires_prompt(client):
    response = client.post(
        "/api/projects/proj_1/videos/generate",
        json={
            "target_id": "shot_01",
            "model_id": "model_video",
            "prompt": "",
        },
    )

    assert response.status_code == 422


def _create_project_with_shot(client, dialogue: str) -> str:
    response = client.post(
        "/api/projects",
        json={"name": "p", "description": ""},
    )
    assert response.status_code == 201
    project_id = response.json()["id"]
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', ?, NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', ?, 'scene1', 1, 0, '', '', '', '', '', ?, 5, '', NULL, ?, ?)",
            (project_id, dialogue, now, now),
        )
    return project_id


def _capture_create_job(service, calls: dict, monkeypatch):
    def fake_create_job(model_id, capability, prompt, **kwargs):
        calls.update({"model_id": model_id, "capability": capability, "prompt": prompt})
        calls.update(kwargs)
        return {"job_id": "job_1", "status": "queued"}

    monkeypatch.setattr(service.generation_service, "create_job", fake_create_job)
    # 默认模拟一个支持原生对白（video_dialogue）的视频模型
    monkeypatch.setattr(
        service.generation_service.manager.repo,
        "get_model",
        lambda model_id: SimpleNamespace(capabilities=["video_dialogue"]),
    )
    monkeypatch.setattr(
        service.versions,
        "get_current",
        lambda *a, **k: SimpleNamespace(file_path="img.png"),
    )


def test_start_shot_video_appends_dialogue_when_with_audio(client, monkeypatch):
    project_id = _create_project_with_shot(client, "你好，快走。")
    service = client.app.state.video_generation_service
    calls = {}
    _capture_create_job(service, calls, monkeypatch)

    service.start_shot_video(
        project_id, "shot1", "model_video", "镜头缓缓推进", with_audio=True
    )

    assert calls["prompt"] == "镜头缓缓推进\n\n对白：你好，快走。"


def test_start_shot_video_skips_dialogue_already_in_prompt(client, monkeypatch):
    project_id = _create_project_with_shot(client, "你好，快走。")
    service = client.app.state.video_generation_service
    calls = {}
    _capture_create_job(service, calls, monkeypatch)

    service.start_shot_video(
        project_id,
        "shot1",
        "model_video",
        "镜头缓缓推进，人物说：你好，快走。",
        with_audio=True,
    )

    assert calls["prompt"] == "镜头缓缓推进，人物说：你好，快走。"


def test_start_shot_video_ignores_dialogue_without_audio(client, monkeypatch):
    project_id = _create_project_with_shot(client, "你好，快走。")
    service = client.app.state.video_generation_service
    calls = {}
    _capture_create_job(service, calls, monkeypatch)

    service.start_shot_video(
        project_id, "shot1", "model_video", "镜头缓缓推进", with_audio=False
    )

    assert calls["prompt"] == "镜头缓缓推进"


def test_start_shot_video_audio_only_model_skips_dialogue(client, monkeypatch):
    """仅支持原生音效（video_audio）的模型即使 with_audio=True 也不应写入对白。"""
    project_id = _create_project_with_shot(client, "你好，快走。")
    service = client.app.state.video_generation_service
    calls = {}
    _capture_create_job(service, calls, monkeypatch)
    monkeypatch.setattr(
        service.generation_service.manager.repo,
        "get_model",
        lambda model_id: SimpleNamespace(capabilities=["video_audio"]),
    )

    service.start_shot_video(
        project_id, "shot1", "model_video", "镜头缓缓推进", with_audio=True
    )

    assert calls["prompt"] == "镜头缓缓推进"
    assert calls["extra"]["strip_audio"] is False


def test_start_shot_video_marks_strip_audio_when_silent(client, monkeypatch):
    """未选择带音频时，落库前应标记移除音轨（strip_audio=True）。"""
    project_id = _create_project_with_shot(client, "你好，快走。")
    service = client.app.state.video_generation_service
    calls = {}
    _capture_create_job(service, calls, monkeypatch)

    service.start_shot_video(
        project_id, "shot1", "model_video", "镜头缓缓推进", with_audio=False
    )

    assert calls["extra"]["strip_audio"] is True
