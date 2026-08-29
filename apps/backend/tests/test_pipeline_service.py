"""一键生产编排测试：模型检查 / 阶段完成判定 / 顺序执行与暂停。"""

from types import SimpleNamespace

import pytest

from app.db.database import get_connection, init_db
from app.schemas.script import AiEpisodePlan, AiEpisodeScriptResult, AiShotsResult
from app.services.pipeline_service import PipelineService


class _Model:
    def __init__(self, model_id, model_type, capabilities):
        self.id = model_id
        self.model_id = model_id
        self.model_type = model_type
        self.capabilities = capabilities
        self.enabled = True


class _FakeRepo:
    def __init__(self, models=None):
        self.models = models or {}

    def list_models(self, model_type=None, enabled_only=True):
        return [
            m
            for m in self.models.values()
            if m.model_type == model_type and m.enabled
        ]


class _FakeReviewServices:
    def __init__(self):
        self.visual_jobs = 0
        self.story_jobs = 0
        self.dialogue_jobs = 0

    def create_model_review_job(
        self, store, project_id, shot_id, *, model_id, review_type=None, script_model_id=None
    ):
        if review_type == "character":
            self.visual_jobs += 1
        elif script_model_id:
            self.dialogue_jobs += 1
        else:
            self.story_jobs += 1
        return SimpleNamespace(id=f"rv_{shot_id}_{self.visual_jobs + self.story_jobs + self.dialogue_jobs}")


class _FakeManager:
    def __init__(self, models=None):
        self.repo = _FakeRepo(models)


class _FakeServices:
    def __init__(self):
        self.story_started = False
        self.script_calls = 0
        self.asset_started = False
        self.shot_calls = 0
        self.image_jobs = 0
        self.video_jobs = 0

    def start(self, project_id, novel_id=None, model_id=None):
        self.story_started = True
        self.asset_started = True
        return {"job_id": "story_1", "project_id": project_id}

    def get(self, job_id):
        return {"status": "completed", "error": None}

    def generate_episode_script(self, project_id, novel_id, model_id):
        self.script_calls += 1
        return AiEpisodeScriptResult(
            episode=AiEpisodePlan(title="第一集", summary=""),
            scenes=[],
        )

    def generate_shots(self, project_id, scene_id, model_id):
        self.shot_calls += 1
        return AiShotsResult(shots=[])

    def image_start(self, project_id, shot_id, model_id, capability):
        self.image_jobs += 1
        return {"job_id": f"img_{shot_id}"}

    def video_start(self, project_id, shot_id, model_id, prompt, duration, with_audio):
        self.video_jobs += 1
        return {"job_id": f"vid_{shot_id}"}


class _FakeStore:
    def __init__(self):
        self.paused = False

    def create(self, *args, **kwargs):
        return SimpleNamespace(id="pipe_1", project_id="p", type="pipeline")

    def get(self, job_id):
        return SimpleNamespace(status="completed", error=None)

    def pause(self, job_id):
        self.paused = True


def _setup(tmp_path, manager=None) -> tuple:
    db_path = tmp_path / "test.db"
    init_db(db_path)
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO projects (id, name, description, created_at, updated_at) VALUES ('p', 'p', '', ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO novels (id, project_id, title, content, source_type, ai_brief, deleted_at, created_at, updated_at) VALUES ('nov1', 'p', '测试小说', '正文', 'original', '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO chapters (id, project_id, novel_id, title, content, order_index, deleted_at, created_at, updated_at) VALUES ('chap1', 'p', 'nov1', '第一章', '内容', 0, NULL, ?, ?)",
            (now, now),
        )
    services = _FakeServices()
    services.visual_review_service = _FakeReviewServices()
    services.story_consistency_service = _FakeReviewServices()
    services.dialogue_review_service = _FakeReviewServices()
    service = PipelineService(
        db_path,
        manager or _FakeManager(),
        story_service=services,
        ai_script_service=services,
        asset_service=services,
        image_generation_service=services,
        video_generation_service=services,
        asset_version_service=None,
        visual_review_service=services.visual_review_service,
        story_consistency_service=services.story_consistency_service,
        dialogue_review_service=services.dialogue_review_service,
    )
    return db_path, service, services


def test_plan_marks_missing_models(tmp_path):
    _db, service, _services = _setup(tmp_path, _FakeManager({}))
    plan = service.plan("p")
    assert plan["can_start"] is False
    assert all(s["status"] == "not_ready" for s in plan["stages"])
    assert any("文本模型" in s["missing_reason"] for s in plan["stages"])
    assert any("图片模型" in s["missing_reason"] for s in plan["stages"])
    assert any("视频模型" in s["missing_reason"] for s in plan["stages"])


def test_start_rejects_without_models(tmp_path):
    _db, service, _services = _setup(tmp_path, _FakeManager({}))
    with pytest.raises(Exception) as exc_info:
        service.start(_FakeStore(), "p")
    assert "无法开始" in str(exc_info.value)


def test_plan_marks_completed_stages(tmp_path):
    db_path, service, _services = _setup(
        tmp_path,
        _FakeManager(
            {
                "m_llm": _Model("m_llm", "llm", []),
                "m_img": _Model("m_img", "image", ["text_to_image"]),
            }
        ),
    )
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO episodes (id, project_id, novel_id, title, summary, order_index, source_chapter_index, deleted_at, created_at, updated_at) VALUES ('ep1', 'p', NULL, '', '', 0, NULL, NULL, ?, ?)",
            (now, now),
        )
    plan = service.plan("p")
    by_key = {s["key"]: s for s in plan["stages"]}
    assert by_key["script"]["status"] == "completed"
    assert by_key["novel_analysis"]["status"] == "ready"
    assert by_key["shot_images"]["status"] == "ready"
    assert by_key["novel_analysis"]["model_id"] == "m_llm"
    assert by_key["shot_images"]["model_id"] == "m_img"


def test_run_executes_stages_and_pauses(tmp_path):
    db_path, service, services = _setup(
        tmp_path,
        _FakeManager(
            {
                "m_llm": _Model("m_llm", "llm", []),
                "m_img": _Model("m_img", "image", ["text_to_image"]),
            }
        ),
    )
    store = _FakeStore()
    job = SimpleNamespace(
        id="pipe_1",
        project_id="p",
        input_payload={"project_id": "p", "auto_continue": False, "include_videos": False},
    )
    service.start(store, "p")  # 重置 pipelines 表

    completed = service.run(job, store)

    assert completed is False
    assert store.paused is True  # 阶段后暂停等确认
    assert services.story_started is True
    assert services.script_calls == 0  # 首阶段后即暂停
    status = service.status("p")
    by_key = {s["stage_key"]: s for s in status["stages"]}
    assert by_key["novel_analysis"]["status"] == "completed"
    assert by_key["script"]["status"] == "queued"  # 未开始

    # 用户多次确认后恢复执行，直至全部完成
    guard = 0
    completed = False
    while not completed and guard < 10:
        store.paused = False
        completed = service.run(job, store)
        guard += 1
    assert completed is True
    assert services.script_calls == 1
    assert services.asset_started is True
    status = service.status("p")
    assert all(s["status"] == "completed" for s in status["stages"])


def test_run_auto_continue_completes(tmp_path):
    db_path, service, services = _setup(
        tmp_path,
        _FakeManager(
            {
                "m_llm": _Model("m_llm", "llm", []),
                "m_img": _Model("m_img", "image", ["text_to_image"]),
            }
        ),
    )
    store = _FakeStore()
    job = SimpleNamespace(
        id="pipe_1",
        project_id="p",
        input_payload={"project_id": "p", "auto_continue": True, "include_videos": False},
    )
    service.start(store, "p")

    completed = service.run(job, store)

    assert completed is True
    assert store.paused is False
    status = service.status("p")
    by_key = {s["stage_key"]: s for s in status["stages"]}
    assert all(s["status"] == "completed" for s in status["stages"])


def test_plan_review_requires_vision_and_llm(tmp_path):
    _db, service, _services = _setup(
        tmp_path,
        _FakeManager({"m_llm": _Model("m_llm", "llm", [])}),
    )
    plan = service.plan("p")
    review = next(s for s in plan["stages"] if s["key"] == "quality_review")
    assert review["status"] == "not_ready"
    assert "视觉" in review["missing_reason"]


def test_start_filters_review_stage(tmp_path):
    _db, service, _services = _setup(
        tmp_path,
        _FakeManager(
            {
                "m_llm": _Model("m_llm", "llm", []),
                "m_vision": _Model("m_vision", "llm", ["vision"]),
                "m_img": _Model("m_img", "image", ["text_to_image"]),
            }
        ),
    )
    store = _FakeStore()
    service.start(store, "p", quality_review=False)
    assert all(
        s["stage_key"] != "quality_review" for s in service.status("p")["stages"]
    )
    service.start(store, "p", quality_review=True)
    assert any(
        s["stage_key"] == "quality_review" for s in service.status("p")["stages"]
    )


def test_run_quality_review_executes_reviews(tmp_path):
    db_path, service, services = _setup(
        tmp_path,
        _FakeManager(
            {
                "m_llm": _Model("m_llm", "llm", []),
                "m_vision": _Model("m_vision", "llm", ["vision"]),
                "m_img": _Model("m_img", "image", ["text_to_image"]),
            }
        ),
    )
    # 构造一个有分镜图的镜头
    with get_connection(db_path) as conn:
        now = "2026-08-16T00:00:00Z"
        conn.execute(
            "INSERT INTO scenes (id, project_id, episode_id, novel_id, title, order_index, slugline, action, dialogue, deleted_at, created_at, updated_at) VALUES ('scene1', 'p', NULL, NULL, '', 0, '', '', '', NULL, ?, ?)",
            (now, now),
        )
        conn.execute(
            "INSERT INTO shots (id, project_id, scene_id, shot_number, order_index, shot_type, camera, characters, action, lighting, dialogue, duration, prompt, deleted_at, created_at, updated_at) VALUES ('shot1', 'p', 'scene1', 1, 0, '', '', '', '', '', '', 5, '', NULL, ?, ?)",
            (now, now),
        )
        # 前面阶段标记完成，只执行质量审查
        for key in (
            "novel_analysis",
            "script",
            "assets",
            "storyboard",
            "shot_images",
            "videos",
            "quality_review",
        ):
            status = "completed" if key != "quality_review" else "queued"
            conn.execute(
                "INSERT INTO pipelines (project_id, stage_key, status, message, updated_at) VALUES ('p', ?, ?, '', ?)",
                (key, status, now),
            )
    from app.services.asset_version_service import AssetVersionService

    f = tmp_path / "shot.png"
    f.write_bytes(b"fake")
    AssetVersionService(db_path, tmp_path / "projects").add_version(
        "p",
        "shot",
        "shot1",
        source_path=f,
        file_ext="png",
    )

    store = _FakeStore()
    job = SimpleNamespace(
        id="pipe_1",
        project_id="p",
        input_payload={
            "project_id": "p",
            "auto_continue": True,
            "include_videos": False,
            "quality_review": True,
        },
    )
    completed = service.run(job, store)

    assert completed is True
    assert services.visual_review_service.visual_jobs >= 1
    assert services.story_consistency_service.story_jobs >= 1
    assert services.dialogue_review_service.dialogue_jobs == 0
