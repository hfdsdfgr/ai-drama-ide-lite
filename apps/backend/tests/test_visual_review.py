"""视觉一致性审核测试：模型审核（角色/场景/连续性）、人工审核、决策、API。"""

import json

import pytest

from app.db.database import get_connection, init_db
from app.services.asset_version_service import AssetVersionService
from app.services.visual_review_service import VisualReviewService


class _Model:
    def __init__(self):
        self.id = "m_vision"
        self.model_id = "m_vision"
        self.model_type = "llm"
        self.capabilities = ["vision"]
        self.enabled = True
        self.provider_id = "prov"
        self.provider_preset_key = ""


class _FakeRepo:
    def get_model(self, model_id):
        if model_id == "m_vision":
            return _Model()
        raise KeyError(model_id)


class _FakeManager:
    def __init__(self, payload=None):
        self.repo = _FakeRepo()
        self.payload = payload or {"consistent": False, "issue": "角色服装颜色不一致"}

    def chat(self, model_id, messages, temperature=0.1, timeout=60):
        # 验证多模态 content 已携带图片
        content = messages[-1]["content"]
        assert isinstance(content, list)
        assert any(item.get("type") == "image_url" for item in content)
        return json.dumps(self.payload, ensure_ascii=False)


def _setup_project(tmp_path) -> tuple:
    db_path = tmp_path / "test.db"
    projects_dir = tmp_path / "projects"
    init_db(db_path)
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', 'p', '', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', 'p', NULL, NULL, '', 0, '雨夜小巷', '', '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', 'p', 'scene1', 1, 0, '', '', '林凡', '走进来', '', '', 5, '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot2', 'p', 'scene1', 2, 1, '', '', '林凡', '抬头', '', '', 5, '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, negative_prompt, model_id, version, created_at, updated_at) VALUES ('a_char', 'p', 'character', '林凡', '黑发', '', '', 1, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO assets (id, project_id, asset_type, name, prompt, negative_prompt, model_id, version, created_at, updated_at) VALUES ('a_loc', 'p', 'location', '雨夜小巷', '石板路', '', '', 1, ?, ?)",
            (now, now),
        )
    versions = AssetVersionService(db_path, projects_dir)
    # 假图片文件即可（审核只读取路径传给模型，测试用 mock manager）
    for entity_type, entity_id in (
        ("character", "a_char"),
        ("location", "a_loc"),
        ("shot", "shot1"),
        ("shot", "shot2"),
    ):
        f = tmp_path / f"{entity_type}_{entity_id}.png"
        f.write_bytes(b"fake-image")
        versions.add_version(
            "p",
            entity_type,
            entity_id,
            source_path=f,
            file_ext="png",
        )
    return db_path, projects_dir, versions


def _make_job(store, shot_id, review_type):
    class _Job:
        pass

    job = _Job()
    job.id = "job_vrev"
    job.project_id = "p"
    job.type = "visual_review"
    job.model_id = "m_vision"
    job.capability = "visual_review"
    job.input_payload = {
        "shot_id": shot_id,
        "model_id": "m_vision",
        "review_type": review_type,
    }
    return job


def test_character_review_flags_mismatch(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(db_path, _FakeManager(), versions, projects_dir)

    result = service.run_model_review(_make_job(None, "shot1", "character"), None)

    assert result["status"] == "flagged"
    assert result["review_type"] == "character"
    review = service.reviews.list_for_shot("p", "shot1")[0]
    assert review["mode"] == "model"
    assert review["status"] == "flagged"
    assert "服装" in review["issue"]


def test_scene_review_passes(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(
        db_path,
        _FakeManager({"consistent": True, "issue": ""}),
        versions,
        projects_dir,
    )

    result = service.run_model_review(_make_job(None, "shot1", "scene"), None)

    assert result["status"] == "passed"
    assert result["issue"] == ""


def test_continuity_review_uses_previous_shot(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )

    # shot2 的连续性审核应对比 shot1 的分镜图
    result = service.run_model_review(_make_job(None, "shot2", "continuity"), None)
    assert result["status"] == "flagged"


def test_costume_review_uses_character_ref_and_previous_shot(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )

    result = service.run_model_review(_make_job(None, "shot2", "costume"), None)

    assert result["status"] == "flagged"
    assert result["review_type"] == "costume"
    review = service.reviews.list_for_shot("p", "shot2")[0]
    assert review["review_type"] == "costume"


def test_continuity_review_no_previous_shot(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )

    with pytest.raises(Exception) as exc_info:
        service.run_model_review(_make_job(None, "shot1", "continuity"), None)
    assert "参考图" in str(exc_info.value)


def test_costume_review_without_character_ref_rejected(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )
    # shot1 无前一镜头、且无角色资产匹配（_setup 里有林凡角色资产，这里删除）
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM assets")
    with pytest.raises(Exception) as exc_info:
        service.run_model_review(_make_job(None, "shot1", "costume"), None)
    assert "参考图" in str(exc_info.value)


def test_manual_review_and_decision(tmp_path):
    db_path, projects_dir, versions = _setup_project(tmp_path)
    service = VisualReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )

    review = service.create_manual_review(
        "p", "shot1", review_type="character", consistent=False, issue="服装不对"
    )
    assert review["status"] == "flagged"
    assert review["issue"] == "服装不对"

    updated = service.set_decision("p", review["id"], decision="keep")
    assert updated["decision"] == "keep"


def test_visual_review_api_manual_and_decision(client, tmp_path):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', ?, NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', ?, 'scene1', 1, 0, '', '', '', '', '', '', 5, '', NULL, ?, ?)",
            (project_id, now, now),
        )
    f = tmp_path / "shot.png"
    f.write_bytes(b"fake")
    client.app.state.asset_version_service.add_version(
        project_id,
        "shot",
        "shot1",
        source_path=f,
        file_ext="png",
    )

    response = client.post(
        f"/api/projects/{project_id}/visual-reviews/manual",
        json={
            "shot_id": "shot1",
            "review_type": "character",
            "consistent": False,
            "issue": "发型不一致",
        },
    )
    assert response.status_code == 201
    review_id = response.json()["id"]
    assert response.json()["status"] == "flagged"

    listed = client.get(
        f"/api/projects/{project_id}/visual-reviews",
        params={"shot_id": "shot1"},
    ).json()
    assert len(listed) == 1

    decision = client.post(
        f"/api/projects/{project_id}/visual-reviews/{review_id}/decision",
        json={"decision": "regenerate"},
    ).json()
    assert decision["decision"] == "regenerate"
