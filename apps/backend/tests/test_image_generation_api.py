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
