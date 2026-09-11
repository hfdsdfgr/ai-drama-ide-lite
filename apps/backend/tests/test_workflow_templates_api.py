"""Project-local workflow templates: isolation, explicit merge, and revision checks."""

from app.db.database import get_connection


def _project_episode(client, suffix: str) -> tuple[str, str]:
    project_id = client.post("/api/projects", json={"name": f"项目{suffix}"}).json()["id"]
    episode_id = f"episode_{suffix}"
    now = "2026-09-11T00:00:00Z"
    with get_connection(client.app.state.settings.db_path) as conn:
        conn.execute(
            "INSERT INTO episodes (id, project_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            (episode_id, project_id, f"第{suffix}集", now, now),
        )
    return project_id, episode_id


def _config(*, auto_continue=False, image_ratio="", videos=False):
    return {
        "auto_continue": auto_continue,
        "storyboard": {"enabled": True, "model_id": "", "capability": "llm"},
        "shot_images": {
            "enabled": True,
            "model_id": "",
            "capability": "text_to_image",
            "aspect_ratio": image_ratio,
        },
        "videos": {
            "enabled": videos,
            "model_id": "",
            "capability": "image_to_video",
            "aspect_ratio": "",
            "duration_mode": "shot",
            "duration": 5,
        },
    }


def test_template_is_project_local_and_applies_selected_fields(client):
    project_a, episode_a = _project_episode(client, "A")
    project_b, _episode_b = _project_episode(client, "B")
    created = client.post(
        f"/api/projects/{project_a}/workflow-templates",
        json={"name": "竖屏快制", "config": _config(auto_continue=True, image_ratio="9:16")},
    )
    assert created.status_code == 201
    template = created.json()
    assert client.get(f"/api/projects/{project_b}/workflow-templates").json() == []
    assert client.get(f"/api/projects/{project_b}/workflow-templates/{template['id']}").status_code == 404

    preview = client.post(
        f"/api/projects/{project_a}/episodes/{episode_a}/workflow-config/preview-template",
        json={"template_id": template["id"]},
    ).json()
    assert {item["field_path"] for item in preview["differences"]} == {
        "auto_continue",
        "shot_images.aspect_ratio",
    }
    applied = client.post(
        f"/api/projects/{project_a}/episodes/{episode_a}/workflow-config/apply-template",
        json={
            "template_id": template["id"],
            "template_revision": preview["template_revision"],
            "config_revision": preview["config_revision"],
            "selected_fields": ["shot_images.aspect_ratio"],
        },
    )
    assert applied.status_code == 200
    assert applied.json()["config"]["shot_images"]["aspect_ratio"] == "9:16"
    assert applied.json()["config"]["auto_continue"] is False


def test_stale_preview_and_unknown_config_fields_are_rejected(client):
    project_id, episode_id = _project_episode(client, "C")
    template = client.post(
        f"/api/projects/{project_id}/workflow-templates",
        json={"name": "模板", "config": _config(auto_continue=True)},
    ).json()
    preview = client.post(
        f"/api/projects/{project_id}/episodes/{episode_id}/workflow-config/preview-template",
        json={"template_id": template["id"]},
    ).json()
    changed = client.put(
        f"/api/projects/{project_id}/episodes/{episode_id}/workflow-config",
        json={"expected_revision": 0, "config": _config(image_ratio="16:9")},
    )
    assert changed.status_code == 200
    stale = client.post(
        f"/api/projects/{project_id}/episodes/{episode_id}/workflow-config/apply-template",
        json={
            "template_id": template["id"],
            "template_revision": preview["template_revision"],
            "config_revision": preview["config_revision"],
            "selected_fields": ["auto_continue"],
        },
    )
    assert stale.status_code == 409

    invalid = _config()
    invalid["api_key"] = "must-not-persist"
    assert client.post(
        f"/api/projects/{project_id}/workflow-templates",
        json={"name": "非法模板", "config": invalid},
    ).status_code == 422


def test_delete_template_keeps_applied_episode_config(client):
    project_id, episode_id = _project_episode(client, "D")
    template = client.post(
        f"/api/projects/{project_id}/workflow-templates",
        json={"name": "模板", "config": _config(image_ratio="1:1")},
    ).json()
    preview = client.post(
        f"/api/projects/{project_id}/episodes/{episode_id}/workflow-config/preview-template",
        json={"template_id": template["id"]},
    ).json()
    applied = client.post(
        f"/api/projects/{project_id}/episodes/{episode_id}/workflow-config/apply-template",
        json={
            "template_id": template["id"],
            "template_revision": preview["template_revision"],
            "config_revision": preview["config_revision"],
            "selected_fields": ["shot_images.aspect_ratio"],
        },
    )
    assert applied.status_code == 200, applied.text
    assert client.delete(
        f"/api/projects/{project_id}/workflow-templates/{template['id']}"
    ).status_code == 204
    saved = client.get(
        f"/api/projects/{project_id}/episodes/{episode_id}/workflow-config"
    ).json()
    assert saved["config"]["shot_images"]["aspect_ratio"] == "1:1"
