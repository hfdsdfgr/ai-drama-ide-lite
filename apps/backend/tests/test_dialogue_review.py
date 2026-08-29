"""台词审核测试：模型审核、人工审核、决策、API。"""

import subprocess

import pytest

from app.db.database import get_connection, init_db
from app.services.adapters.base import GenerationResult
from app.services.asset_version_service import AssetVersionService
from app.services.dialogue_review_service import DialogueReviewService
from app.services.media_mix import ffmpeg_exe


class _Model:
    def __init__(self, model_id, model_type, capabilities):
        self.id = model_id
        self.model_id = model_id
        self.model_type = model_type
        self.capabilities = capabilities
        self.enabled = True
        self.provider_id = "prov"
        self.provider_preset_key = ""


class _FakeRepo:
    def get_model(self, model_id):
        if model_id == "m_asr":
            return _Model("m_asr", "audio", ["speech_to_text"])
        if model_id == "m_llm":
            return _Model("m_llm", "llm", [])
        raise KeyError(model_id)


class _FakeManager:
    def __init__(self, detected_text="你好，快走。", chat_payload=None):
        self.repo = _FakeRepo()
        self.detected_text = detected_text
        self.chat_calls = 0
        self.chat_payload = chat_payload or {
            "consistent": False,
            "issue": "台词说成了别的内容",
        }

    def generate(self, model_id, capability, request):
        assert capability == "speech_to_text"
        return GenerationResult(urls=[], meta={"text": self.detected_text})

    def chat(self, model_id, messages, temperature=0.1, timeout=60):
        self.chat_calls += 1
        return __import__("json").dumps(self.chat_payload, ensure_ascii=False)


def _make_video(path, seconds=2, with_audio=False):
    cmd = [
        ffmpeg_exe(),
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=red:s=320x240:d={seconds}",
    ]
    if with_audio:
        cmd += ["-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}"]
    cmd += ["-c:v", "libx264", "-pix_fmt", "yuv420p"]
    if with_audio:
        cmd += ["-c:a", "aac", "-shortest"]
    cmd.append(str(path))
    subprocess.run(cmd, check=True, capture_output=True)


def _setup_project(tmp_path, with_audio=True) -> tuple:
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
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', 'p', NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', 'p', 'scene1', 1, 0, '', '', '', '', '', '你好，快走。', 5, '', NULL, ?, ?)",
            (now, now),
        )
    versions = AssetVersionService(db_path, projects_dir)
    video = tmp_path / "shot.mp4"
    _make_video(video, with_audio=with_audio)
    record = versions.add_version(
        "p",
        "shot_video",
        "shot1",
        source_path=video,
        file_ext="mp4",
    )
    return db_path, projects_dir, versions, record


def test_model_review_flags_mismatch(tmp_path):
    db_path, projects_dir, versions, video_record = _setup_project(tmp_path)
    service = DialogueReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )
    store = _StubStore()
    job = store.create(
        "dialogue_review",
        "p",
        model_id="m_asr",
        capability="dialogue_review",
        input_payload={
            "shot_id": "shot1",
            "model_id": "m_asr",
            "script_model_id": "m_llm",
        },
    )

    result = service.run_model_review(job, store)

    assert result["status"] == "flagged"
    assert result["detected_speech"] == "你好，快走。"
    review = service.reviews.list_for_shot("p", "shot1")[0]
    assert review["mode"] == "model"
    assert review["video_version_id"] == video_record.id
    assert review["status"] == "flagged"
    assert review["expected_dialogue"] == "你好，快走。"


def test_model_review_passes_when_consistent(tmp_path):
    db_path, projects_dir, versions, _ = _setup_project(tmp_path)
    manager = _FakeManager(
        detected_text="你好，快走。",
        chat_payload={"consistent": True, "issue": ""},
    )
    service = DialogueReviewService(db_path, manager, versions, projects_dir)
    job = _StubStore().create(
        "dialogue_review",
        "p",
        model_id="m_asr",
        capability="dialogue_review",
        input_payload={
            "shot_id": "shot1",
            "model_id": "m_asr",
            "script_model_id": "m_llm",
        },
    )

    result = service.run_model_review(job, _StubStore())

    assert result["status"] == "passed"
    assert result["issue"] == ""


def test_model_review_flags_when_no_speech(tmp_path):
    """转写为空（视频无人声）应标记 flagged，而不是让任务失败，且不调用 LLM 比对。"""
    db_path, projects_dir, versions, video_record = _setup_project(tmp_path)
    manager = _FakeManager(detected_text="")
    service = DialogueReviewService(db_path, manager, versions, projects_dir)
    job = _StubStore().create(
        "dialogue_review",
        "p",
        model_id="m_asr",
        capability="dialogue_review",
        input_payload={
            "shot_id": "shot1",
            "model_id": "m_asr",
            "script_model_id": "m_llm",
        },
    )

    result = service.run_model_review(job, _StubStore())

    assert result["status"] == "flagged"
    assert result["detected_speech"] == ""
    assert "未检测到语音" in result["issue"]
    assert manager.chat_calls == 0
    review = service.reviews.list_for_shot("p", "shot1")[0]
    assert review["status"] == "flagged"
    assert review["video_version_id"] == video_record.id


def test_model_review_flags_when_video_has_no_audio_track(tmp_path):
    """视频完全没有音轨时应标记 flagged（未检测到语音），而不是报错。"""
    db_path, projects_dir, versions, _ = _setup_project(tmp_path, with_audio=False)
    manager = _FakeManager(detected_text="")
    service = DialogueReviewService(db_path, manager, versions, projects_dir)
    job = _StubStore().create(
        "dialogue_review",
        "p",
        model_id="m_asr",
        capability="dialogue_review",
        input_payload={
            "shot_id": "shot1",
            "model_id": "m_asr",
            "script_model_id": "m_llm",
        },
    )

    result = service.run_model_review(job, _StubStore())

    assert result["status"] == "flagged"
    assert "没有音轨" in result["issue"]
    assert manager.chat_calls == 0


def test_manual_review_and_decision(tmp_path):
    db_path, projects_dir, versions, _ = _setup_project(tmp_path)
    service = DialogueReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )

    review = service.create_manual_review(
        "p", "shot1", consistent=False, detected_speech="别的台词"
    )
    assert review["mode"] == "manual"
    assert review["status"] == "flagged"
    assert review["detected_speech"] == "别的台词"

    updated = service.set_decision("p", review["id"], decision="keep")
    assert updated["decision"] == "keep"


def test_review_requires_video(tmp_path):
    db_path, projects_dir, versions, _ = _setup_project(tmp_path)
    service = DialogueReviewService(
        db_path, _FakeManager(), versions, projects_dir
    )
    # 删除视频版本后审核应报错
    with get_connection(db_path) as conn:
        conn.execute("DELETE FROM versions")
    with pytest.raises(Exception) as exc_info:
        service.create_manual_review("p", "shot1", consistent=True)
    assert "还没有生成视频" in str(exc_info.value)


def test_review_api_manual_and_decision(client, tmp_path):
    project_id = client.post("/api/projects", json={"name": "p"}).json()["id"]
    db_path = client.app.state.settings.db_path
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', ?, NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (project_id, now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', ?, 'scene1', 1, 0, '', '', '', '', '', '你好。', 5, '', NULL, ?, ?)",
            (project_id, now, now),
        )
    video = tmp_path / "shot.mp4"
    _make_video(video, with_audio=True)
    client.app.state.asset_version_service.add_version(
        project_id,
        "shot_video",
        "shot1",
        source_path=video,
        file_ext="mp4",
    )

    response = client.post(
        f"/api/projects/{project_id}/dialogue-reviews/manual",
        json={"shot_id": "shot1", "consistent": False, "detected_speech": "不对"},
    )
    assert response.status_code == 201
    review_id = response.json()["id"]
    assert response.json()["status"] == "flagged"

    listed = client.get(
        f"/api/projects/{project_id}/dialogue-reviews",
        params={"shot_id": "shot1"},
    ).json()
    assert len(listed) == 1

    decision = client.post(
        f"/api/projects/{project_id}/dialogue-reviews/{review_id}/decision",
        json={"decision": "regenerate"},
    ).json()
    assert decision["decision"] == "regenerate"


class _StubStore:
    """简化 Job 对象：真实 store 仅用于 create/get，测试只需对象。"""

    def create(
        self,
        job_type,
        project_id,
        *,
        model_id="",
        provider_id="",
        capability="",
        input_payload=None,
    ):
        class _Job:
            pass

        job = _Job()
        job.id = "job_review"
        job.project_id = project_id
        job.type = job_type
        job.model_id = model_id
        job.provider_id = provider_id
        job.capability = capability
        job.input_payload = input_payload or {}
        return job
