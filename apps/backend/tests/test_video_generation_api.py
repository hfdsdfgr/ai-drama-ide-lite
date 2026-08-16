"""Phase 14 M1 - Video generation API route tests."""


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
