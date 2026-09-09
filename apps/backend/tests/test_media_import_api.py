from datetime import datetime, timezone

from app.db.database import get_connection


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _setup(client) -> tuple[str, str, str]:
    project_id = client.post("/api/projects", json={"name": "导入项目"}).json()["id"]
    now = _now()
    with get_connection(client.app.state.settings.db_path) as conn:
        conn.execute(
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, created_at, updated_at) VALUES ('asset_1', ?, 'character', '林凡', '', ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO episodes (id, project_id, title, created_at, updated_at) VALUES ('episode_1', ?, '第一集', ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, title, created_at, updated_at) VALUES ('scene_1', ?, 'episode_1', '雨夜', ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, order_index, created_at, updated_at) VALUES ('shot_1', ?, 'scene_1', 0, ?, ?)",
            (project_id, now, now),
        )
    return project_id, "asset_1", "shot_1"


def test_imported_media_becomes_current_versions(client):
    project_id, asset_id, shot_id = _setup(client)
    image = ("asset.png", b"fake image", "image/png")

    asset = client.post(
        f"/api/projects/{project_id}/assets/{asset_id}/versions/import",
        files={"file": image},
    )
    assert asset.status_code == 201
    assert asset.json()["payload"]["source"] == "imported"

    shot_image = client.post(
        f"/api/projects/{project_id}/images/shots/{shot_id}/import",
        files={"file": ("shot.webp", b"fake image", "image/webp")},
    )
    assert shot_image.status_code == 201
    assert shot_image.json()["entity_type"] == "shot"

    video = client.post(
        f"/api/projects/{project_id}/videos/{shot_id}/import",
        files={"file": ("shot.mp4", b"fake video", "video/mp4")},
    )
    assert video.status_code == 201
    assert video.json()["entity_type"] == "shot_video"


def test_import_reference_library(client):
    project_id, _asset_id, _shot_id = _setup(client)
    response = client.post(
        f"/api/projects/{project_id}/references/import",
        files={"file": ("水墨风.png", b"fake image", "image/png")},
    )
    assert response.status_code == 201
    listed = client.get(f"/api/projects/{project_id}/references")
    assert listed.status_code == 200
    assert listed.json()[0]["name"] == "水墨风"


def test_import_script_json(client):
    project_id, _asset_id, _shot_id = _setup(client)
    payload = '{"episodes":[{"title":"导入分集","scenes":[{"title":"场景","shots":[{"shot_type":"wide","duration":3}]}]}]}'.encode()
    response = client.post(
        f"/api/projects/{project_id}/script/import",
        files={"file": ("script.json", payload, "application/json")},
    )
    assert response.status_code == 201
    episode_id = response.json()["episode_ids"][0]
    detail = client.get(f"/api/projects/{project_id}/script/episodes/{episode_id}").json()
    scene = client.get(f"/api/projects/{project_id}/script/scenes/{detail['scenes'][0]['id']}").json()
    assert scene["shots"][0]["shot_type"] == "wide"
