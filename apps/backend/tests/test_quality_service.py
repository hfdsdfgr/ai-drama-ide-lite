"""项目级质量报告测试：状态聚合与 API。"""

from app.db.database import get_connection


def _setup(client) -> str:
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', ?, NULL, NULL, '', 0, '雨夜小巷', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        for idx, shot_id in enumerate(("shot1", "shot2", "shot3"), start=1):
            conn.execute(
                "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES (?, ?, 'scene1', ?, ?, '', '', '', '', '', '', 5, '', NULL, ?, ?)",
                (shot_id, project_id, idx, idx, now, now),
            )
    return project_id


def _add_shot_image(client, project_id: str, shot_id: str):
    import tempfile
    from pathlib import Path

    f = Path(tempfile.mkdtemp()) / "shot.png"
    f.write_bytes(b"fake")
    client.app.state.asset_version_service.add_version(
        project_id,
        "shot",
        shot_id,
        source_path=f,
        file_ext="png",
    )


def _add_dialogue_review(client, project_id: str, shot_id: str, status: str):
    with get_connection(client.app.state.settings.db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO shot_dialogue_reviews (id, project_id, shot_id, video_version_id, mode, model_id, status, detected_speech, expected_dialogue, issue, decision, created_at, updated_at) VALUES (?, ?, ?, 'v1', 'manual', '', ?, '实际', '剧本', ?, '', ?, ?)",
            (f"dr_{shot_id}", project_id, shot_id, status, "台词不一致" if status == "flagged" else "", now, now),
        )


def _add_visual_review(client, project_id: str, shot_id: str, review_type: str, status: str):
    with get_connection(client.app.state.settings.db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO shot_visual_reviews (id, project_id, shot_id, image_version_id, review_type, mode, model_id, status, issue, decision, created_at, updated_at) VALUES (?, ?, ?, 'v1', ?, 'manual', '', ?, ?, '', ?, ?)",
            (f"vr_{shot_id}_{review_type}", project_id, shot_id, review_type, status, "服装不一致" if status == "flagged" else "", now, now),
        )


def test_quality_empty_project(client):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    body = client.get(f"/api/projects/{project_id}/quality").json()
    assert body["summary"] == {"flagged": 0, "passed": 0, "pending": 0, "total": 0}
    assert body["items"] == []


def test_quality_statuses(client):
    project_id = _setup(client)
    # shot1: 有图未审核 → pending
    _add_shot_image(client, project_id, "shot1")
    # shot2: 台词 flagged → flagged（覆盖视觉 passed）
    _add_shot_image(client, project_id, "shot2")
    _add_dialogue_review(client, project_id, "shot2", "flagged")
    _add_visual_review(client, project_id, "shot2", "character", "passed")
    # shot3: 全部通过 → passed
    _add_shot_image(client, project_id, "shot3")
    _add_visual_review(client, project_id, "shot3", "scene", "passed")

    body = client.get(f"/api/projects/{project_id}/quality").json()
    summary = body["summary"]
    assert summary == {"flagged": 1, "passed": 1, "pending": 1, "total": 3}

    items = {item["shot_id"]: item for item in body["items"]}
    assert items["shot1"]["status"] == "pending"
    assert items["shot2"]["status"] == "flagged"
    assert items["shot3"]["status"] == "passed"
    assert items["shot2"]["scene_title"] == "雨夜小巷"
    assert items["shot2"]["reviews"][0]["issue"] == "台词不一致"


def test_quality_api_not_found(client):
    response = client.get("/api/projects/proj_missing/quality")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"
