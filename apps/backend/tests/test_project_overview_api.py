"""Phase 15 — 项目生产阶段概览接口测试。"""

import json

from app.db.database import get_connection


def _create_project(client, name="概览项目") -> str:
    client.post("/api/projects", json={"name": name})
    return client.get("/api/projects").json()[0]["id"]


def _now() -> str:
    return "2026-08-16T00:00:00Z"


def _insert(conn, sql: str, params: tuple) -> None:
    conn.execute(sql, params)


def _stage_map(client, pid: str) -> dict[str, dict]:
    body = client.get(f"/api/projects/{pid}/overview").json()
    return {stage["key"]: stage for stage in body["stages"]}


def test_empty_project_all_pending(client):
    pid = _create_project(client)
    response = client.get(f"/api/projects/{pid}/overview")
    assert response.status_code == 200
    body = response.json()
    assert body["project_id"] == pid
    assert [s["key"] for s in body["stages"]] == [
        "novel_analysis",
        "story_bible",
        "character_extraction",
        "script_generation",
        "character_asset",
        "scene_asset",
        "storyboard",
        "image_generation",
        "video_generation",
    ]
    assert all(s["status"] == "pending" for s in body["stages"])


def test_stages_reflect_existing_data(client):
    pid = _create_project(client)
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = _now()
        _insert(
            conn,
            "INSERT INTO novels (id, project_id, title, content, source_type, ai_brief, deleted_at, created_at, updated_at) VALUES (?, ?, ?, ?, 'original', '', NULL, ?, ?)",
            ("nov1", pid, "测试小说", "正文内容", now, now),
        )
        _insert(
            conn,
            "INSERT INTO chapters (id, project_id, novel_id, title, content, order_index, deleted_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, NULL, ?, ?)",
            ("chap1", pid, "nov1", "第一章", "章节内容", now, now),
        )
        bible = {
            "synopsis": "梗概",
            "characters": [],
            "locations": [],
            "props": [],
            "events": [],
            "conflicts": [],
            "plotlines": [],
            "foreshadowing": [],
        }
        _insert(
            conn,
            "INSERT INTO stories (id, project_id, content, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
            ("story1", pid, json.dumps(bible, ensure_ascii=False), now, now),
        )
        _insert(
            conn,
            "INSERT INTO characters (id, project_id, name, description, created_at, updated_at) VALUES (?, ?, ?, '', ?, ?)",
            ("char1", pid, "林凡", now, now),
        )
        _insert(
            conn,
            "INSERT INTO episodes (id, project_id, novel_id, title, summary, order_index, source_chapter_index, deleted_at, created_at, updated_at) VALUES (?, ?, ?, ?, '', 0, NULL, NULL, ?, ?)",
            ("ep1", pid, "nov1", "第一集", now, now),
        )
        _insert(
            conn,
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES (?, ?, ?, ?, ?, 0, '', '', '', NULL, ?, ?)",
            ("sc1", pid, "ep1", "nov1", "第一场", now, now),
        )
        _insert(
            conn,
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES (?, ?, ?, 1, 0, '', '', '', '', '', '', 0, '', NULL, ?, ?)",
            ("shot1", pid, "sc1", now, now),
        )
        _insert(
            conn,
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, negative_prompt, model_id, version, created_at, updated_at) VALUES (?, ?, 'character', '林凡', '', '', '', 1, ?, ?)",
            ("a_char", pid, now, now),
        )
        _insert(
            conn,
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, negative_prompt, model_id, version, created_at, updated_at) VALUES (?, ?, 'location', '青云门', '', '', '', 1, ?, ?)",
            ("a_loc", pid, now, now),
        )
        for entity_type, entity_id in (
            ("character", "a_char"),
            ("location", "a_loc"),
            ("shot", "shot1"),
        ):
            _insert(
                conn,
                "INSERT INTO versions (id, project_id, entity_type, entity_id, version, payload, file_path, model_id, provider_id, job_id, is_current, created_at) VALUES (?, ?, ?, ?, 1, '{}', '', '', '', '', 1, ?)",
                (f"v_{entity_type}", pid, entity_type, entity_id, now),
            )
        _insert(
            conn,
            "INSERT INTO versions (id, project_id, entity_type, entity_id, version, payload, file_path, model_id, provider_id, job_id, is_current, created_at) VALUES (?, ?, 'shot_video', 'shot1', 1, '{}', '', '', '', '', 1, ?)",
            ("v_video", pid, now),
        )

    stages = _stage_map(client, pid)
    for key in (
        "novel_analysis",
        "story_bible",
        "character_extraction",
        "script_generation",
        "character_asset",
        "scene_asset",
        "storyboard",
        "image_generation",
        "video_generation",
    ):
        assert stages[key]["status"] == "completed", key
    assert stages["novel_analysis"]["detail"] == "1 章"
    assert stages["character_extraction"]["detail"] == "1 个角色"


def test_active_character_asset_job_marks_stage_active(client):
    pid = _create_project(client)
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = _now()
        _insert(
            conn,
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, negative_prompt, model_id, version, created_at, updated_at) VALUES (?, ?, 'character', '林凡', '', '', '', 1, ?, ?)",
            ("a_char", pid, now, now),
        )
        payload = json.dumps({"extra": {"target_type": "asset", "target_id": "a_char"}})
        _insert(
            conn,
            "INSERT INTO jobs (id, project_id, type, status, progress, model_id, provider_id, capability, task_id, input_payload, result_payload, output_files, error, error_category, attempts, max_attempts, created_at) VALUES (?, ?, 'generation', 'running', 0, 'model', 'prov', 'text_to_image', '', ?, '{}', '[]', '', '', 1, 1, ?)",
            ("job1", pid, payload, now),
        )

    stages = _stage_map(client, pid)
    assert stages["character_asset"]["status"] == "active"
    assert stages["character_asset"]["detail"] == "生成中"


def test_overview_project_not_found(client):
    response = client.get("/api/projects/proj_missing/overview")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "project_not_found"
