"""剧情一致性审核测试。"""

import json

import pytest

from app.db.database import get_connection, init_db
from app.services.story_consistency_service import StoryConsistencyService


class _Model:
    def __init__(self):
        self.id = "m_llm"
        self.model_id = "m_llm"
        self.model_type = "llm"
        self.capabilities = []
        self.enabled = True
        self.provider_id = "prov"
        self.provider_preset_key = ""


class _FakeRepo:
    def get_model(self, model_id):
        if model_id == "m_llm":
            return _Model()
        raise KeyError(model_id)


class _FakeManager:
    def __init__(self, payload=None):
        self.repo = _FakeRepo()
        self.payload = payload or {
            "consistent": False,
            "issue": "前后动作冲突",
        }

    def chat(self, model_id, messages, temperature=0.1, timeout=60):
        # 验证上下文包含前后镜头
        user = messages[-1]["content"]
        assert "前一镜头" in user
        assert "后一镜头" in user
        return json.dumps(self.payload, ensure_ascii=False)


def _setup(tmp_path) -> tuple:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', 'p', '', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', 'p', NULL, NULL, '', 0, '雨夜', '', '', NULL, ?, ?)",
            (now, now),
        )
        for idx, shot_id, action, dialogue in (
            (1, "shot1", "走进房间", "我回来了"),
            (2, "shot2", "放下雨伞", "外面雨很大"),
            (3, "shot3", "坐下", "喝杯茶吧"),
        ):
            conn.execute(
                "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES (?, 'p', 'scene1', ?, ?, '', '', '', ?, '', ?, 5, '', NULL, ?, ?)",
                (
                    f"shot{idx}",
                    idx,
                    idx,
                    action,
                    dialogue,
                    now,
                    now,
                ),
            )
    return db_path


def _make_job(shot_id):
    class _Job:
        pass

    job = _Job()
    job.id = "job_srev"
    job.project_id = "p"
    job.type = "story_review"
    job.model_id = "m_llm"
    job.capability = "story_review"
    job.input_payload = {"shot_id": shot_id, "model_id": "m_llm"}
    return job


def test_story_review_flags_conflict(tmp_path):
    db_path = _setup(tmp_path)
    service = StoryConsistencyService(db_path, _FakeManager())

    result = service.run_model_review(_make_job("shot2"), None)

    assert result["status"] == "flagged"
    review = service.reviews.list_for_shot("p", "shot2")[0]
    assert review["mode"] == "model"
    assert review["status"] == "flagged"
    assert "冲突" in review["issue"]


def test_story_review_passes(tmp_path):
    db_path = _setup(tmp_path)
    service = StoryConsistencyService(
        db_path,
        _FakeManager({"consistent": True, "issue": ""}),
    )

    result = service.run_model_review(_make_job("shot1"), None)

    assert result["status"] == "passed"


def test_story_manual_review_and_decision(tmp_path):
    db_path = _setup(tmp_path)
    service = StoryConsistencyService(db_path, _FakeManager())

    review = service.create_manual_review(
        "p", "shot1", consistent=False, issue="台词对不上"
    )
    assert review["status"] == "flagged"
    assert review["issue"] == "台词对不上"

    updated = service.set_decision("p", review["id"], decision="keep")
    assert updated["decision"] == "keep"


def test_story_review_api_manual(client):
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

    response = client.post(
        f"/api/projects/{project_id}/story-reviews/manual",
        json={"shot_id": "shot1", "consistent": False, "issue": "剧情断裂"},
    )
    assert response.status_code == 201
    review_id = response.json()["id"]
    assert response.json()["status"] == "flagged"

    listed = client.get(
        f"/api/projects/{project_id}/story-reviews",
        params={"shot_id": "shot1"},
    ).json()
    assert len(listed) == 1

    decision = client.post(
        f"/api/projects/{project_id}/story-reviews/{review_id}/decision",
        json={"decision": "regenerate"},
    ).json()
    assert decision["decision"] == "regenerate"
