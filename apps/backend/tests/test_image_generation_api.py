"""Phase 13 M2 - Image generation API route tests."""


def _job_out(model_id="model_img", capability="text_to_image"):
    return {
        "job_id": "job_1",
        "model_id": model_id,
        "capability": capability,
        "status": "queued",
        "error": None,
        "result": None,
        "created_at": "2026-08-15T00:00:00Z",
    }


def test_generate_asset_image_route(client, monkeypatch):
    calls = {}

    def fake_start_asset(
        project_id,
        asset_id,
        model_id,
        capability="text_to_image",
        *,
        aspect_ratio=None,
        art_style=None,
        negative_prompt="",
        reference_asset_ids=None,
    ):
        calls.update(
            {
                "project_id": project_id,
                "asset_id": asset_id,
                "model_id": model_id,
                "capability": capability,
                "negative_prompt": negative_prompt,
            }
        )
        return _job_out(model_id, capability)

    monkeypatch.setattr(
        client.app.state.image_generation_service,
        "start_asset",
        fake_start_asset,
    )

    response = client.post(
        "/api/projects/proj_1/images/generate",
        json={
            "target_type": "asset",
            "target_id": "character_lin_001",
            "model_id": "model_img",
            "capability": "text_to_image",
            "negative_prompt": "no blur",
        },
    )

    assert response.status_code == 201
    assert response.json()["job_id"] == "job_1"
    assert calls["project_id"] == "proj_1"
    assert calls["asset_id"] == "character_lin_001"
    assert calls["negative_prompt"] == "no blur"


def test_generate_shot_image_route(client, monkeypatch):
    def fake_start_shot(
        project_id,
        shot_id,
        model_id,
        capability="text_to_image",
        *,
        aspect_ratio=None,
        art_style=None,
        negative_prompt="",
        reference_asset_ids=None,
    ):
        return _job_out(model_id, capability)

    monkeypatch.setattr(
        client.app.state.image_generation_service,
        "start_shot",
        fake_start_shot,
    )

    response = client.post(
        "/api/projects/proj_1/images/generate",
        json={
            "target_type": "shot",
            "target_id": "shot_01",
            "model_id": "model_img",
        },
    )

    assert response.status_code == 201
    assert response.json()["capability"] == "text_to_image"


def test_image_generate_requires_valid_target_type(client):
    response = client.post(
        "/api/projects/proj_1/images/generate",
        json={
            "target_type": "unknown",
            "target_id": "shot_01",
            "model_id": "model_img",
        },
    )

    assert response.status_code == 422


def test_explicit_empty_references_survive_route(client, monkeypatch):
    calls = {}
    def capture(*args, **kwargs):
        calls.update(kwargs)
        return _job_out()
    monkeypatch.setattr(client.app.state.image_generation_service, "start_shot", capture)
    response = client.post("/api/projects/proj_1/images/generate", json={
        "target_type": "shot", "target_id": "shot_1", "model_id": "model_img",
        "reference_version_ids": [], "prompt": "新的提示词",
    })
    assert response.status_code == 201
    assert calls["reference_version_ids"] == []
    assert calls["prompt"] == "新的提示词"


def test_batch_image_plan_route(client, monkeypatch):
    monkeypatch.setattr(
        client.app.state.image_generation_service,
        "plan_shots",
        lambda project_id, model_id, shot_ids: {
            "ready": [{"shot_id": "shot_01", "label": "场景 · 镜头 1"}],
            "skipped": [],
        },
    )

    response = client.post(
        "/api/projects/proj_1/images/batch-plan",
        json={"model_id": "model_img", "shot_ids": ["shot_01"]},
    )

    assert response.status_code == 200
    assert response.json()["ready"][0]["shot_id"] == "shot_01"


def test_batch_image_generate_route(client, monkeypatch):
    monkeypatch.setattr(
        client.app.state.image_generation_service,
        "start_shots",
        lambda project_id, model_id, shot_ids, batch_label: {
            "batch_id": "batch_1",
            "jobs": [_job_out()],
            "ready": [{"shot_id": "shot_01", "label": "场景 · 镜头 1"}],
            "skipped": [],
        },
    )

    response = client.post(
        "/api/projects/proj_1/images/batch-generate",
        json={
            "model_id": "model_img",
            "shot_ids": ["shot_01"],
            "batch_label": "第 1 集 · 场景 1",
        },
    )

    assert response.status_code == 201
    assert response.json()["batch_id"] == "batch_1"
    assert response.json()["jobs"][0]["job_id"] == "job_1"
