"""Story Engine 测试（Phase 6）。"""

import json
import time

from app.db.database import get_connection
from app.schemas.story import StoryBible
from app.services.adapters.manager import ProviderManager
from app.services.story_analysis import StoryAnalysisService, _extract_json
from app.services.story_repo import StoryRepository


def _chapter_extraction_json(chapter: int) -> str:
    return json.dumps(
        {
            "chapter_summary": f"第{chapter}章摘要",
            "characters": [
                {
                    "name": "林凡",
                    "aliases": ["林"],
                    "summary": f"主角，第{chapter}章登场",
                    "role_hint": "主角",
                }
            ],
            "locations": [
                {"name": "青云镇", "description": "故事发生的小镇"}
            ],
            "props": [
                {"name": "玉佩", "description": "主角随身信物"}
            ],
            "events": [
                {
                    "summary": f"第{chapter}章事件",
                    "importance": "high",
                    "characters": ["林凡"],
                }
            ],
        },
        ensure_ascii=False,
    )


def _bible_json() -> str:
    return json.dumps(
        {
            "synopsis": "林凡的成长故事",
            "characters": [
                {
                    "name": "林凡",
                    "aliases": ["林"],
                    "summary": "主角",
                    "role_hint": "主角",
                }
            ],
            "locations": [{"name": "青云镇", "description": "小镇"}],
            "props": [{"name": "玉佩", "description": "信物"}],
            "events": [
                {
                    "summary": "第一章事件",
                    "importance": "high",
                    "characters": ["林凡"],
                    "chapter_index": 0,
                }
            ],
            "conflicts": ["林凡与反派冲突"],
            "plotlines": ["成长线"],
            "foreshadowing": ["玉佩来历成谜"],
        },
        ensure_ascii=False,
    )


class _FakeManager:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def chat(self, model_id, messages, temperature=0.8):
        self.calls.append(messages)
        if self.responses:
            return self.responses.pop(0)
        return "{}"


def _wait_terminal(service, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = service.get(job_id)
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not reach terminal state")


def _create_novel_with_chapters(client, count=2):
    project = client.post("/api/projects", json={"name": "故事项目"}).json()
    novel = client.post(
        f"/api/projects/{project['id']}/novels", json={"title": "测试小说"}
    ).json()
    for i in range(count):
        client.post(
            f"/api/projects/{project['id']}/novels/{novel['id']}/chapters",
            json={"title": f"第{i + 1}章", "content": f"第{i + 1}章正文：林凡在青云镇。"},
        )
    return project["id"], novel["id"]


def test_extract_json_handles_fences():
    assert _extract_json('```json\n{"a": 1}\n```') == '{"a": 1}'
    assert _extract_json('前缀 {"a": 1} 后缀') == '{"a": 1}'
    assert _extract_json('{"a": 1}') == '{"a": 1}'


def test_analysis_completes_and_saves_bible(client):
    project_id, novel_id = _create_novel_with_chapters(client, count=2)
    db_path = client.app.state.settings.db_path
    fake = _FakeManager(
        [
            _chapter_extraction_json(1),
            _chapter_extraction_json(2),
            _bible_json(),
        ]
    )
    service = StoryAnalysisService(fake, db_path)
    job = service.start(project_id, novel_id, model_id="model_x", mode="full")
    finished = _wait_terminal(service, job["job_id"])
    assert finished["status"] == "completed"
    assert finished["progress"] == 1.0
    assert "角色" in finished["detail"]

    bible = StoryRepository(db_path).get_bible(project_id)
    assert bible is not None
    assert bible.characters[0].name == "林凡"
    assert bible.plotlines == ["成长线"]


def test_merge_keeps_existing_entities(client):
    project_id, novel_id = _create_novel_with_chapters(client, count=1)
    db_path = client.app.state.settings.db_path
    repo = StoryRepository(db_path)
    existing = StoryBible(
        synopsis="旧简介",
        characters=[{"name": "旧角色", "summary": "旧描述", "role_hint": "配角"}],
    )
    repo.save_bible(project_id, existing)

    fake = _FakeManager([_chapter_extraction_json(1), _bible_json()])
    service = StoryAnalysisService(fake, db_path)
    job = service.start(project_id, novel_id, model_id="model_x", mode="merge")
    finished = _wait_terminal(service, job["job_id"])
    assert finished["status"] == "completed"

    # 合并模式：旧角色保留（upsert 更新），新实体（林凡）入库
    with get_connection(db_path) as conn:
        names = [
            r["name"]
            for r in conn.execute(
                "SELECT name FROM characters WHERE project_id = ?", (project_id,)
            ).fetchall()
        ]
    assert "旧角色" in names
    assert "林凡" in names


def test_invalid_output_repairs_once(client):
    project_id, novel_id = _create_novel_with_chapters(client, count=1)
    db_path = client.app.state.settings.db_path
    fake = _FakeManager(
        [
            "这不是 JSON",  # 抽取失败
            _chapter_extraction_json(1),  # 修复后成功
            _bible_json(),
        ]
    )
    service = StoryAnalysisService(fake, db_path)
    job = service.start(project_id, novel_id, model_id="model_x", mode="full")
    finished = _wait_terminal(service, job["job_id"])
    assert finished["status"] == "completed"
    assert len(fake.calls) == 3  # 2 次抽取（含修复）+ 1 次合并


def test_analysis_requires_chapters(client):
    project = client.post("/api/projects", json={"name": "空项目"}).json()
    novel = client.post(
        f"/api/projects/{project['id']}/novels", json={"title": "空小说"}
    ).json()
    service = StoryAnalysisService(
        _FakeManager([]), client.app.state.settings.db_path
    )
    try:
        service.start(project["id"], novel["id"], "model_x", "full")
    except Exception as exc:
        assert getattr(exc, "code", "") == "no_chapters"
    else:
        raise AssertionError("should raise no_chapters")


# ---------- 接口级 ----------


def _scripted_chat(responses):
    box = {"responses": list(responses)}

    def fake_chat(self, model_id, messages, temperature=0.8):
        if box["responses"]:
            return box["responses"].pop(0)
        return "{}"

    return fake_chat


def test_analysis_endpoint(client, monkeypatch):
    project_id, novel_id = _create_novel_with_chapters(client, count=1)
    monkeypatch.setattr(
        ProviderManager,
        "chat",
        _scripted_chat([_chapter_extraction_json(1), _bible_json()]),
    )
    response = client.post(
        f"/api/projects/{project_id}/story/analysis",
        json={"novel_id": novel_id, "model_id": "model_x", "mode": "full"},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        job = client.get(f"/api/projects/{project_id}/story/analysis/{job_id}").json()
        status = job["status"]
        if status in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert status == "completed"

    bible = client.get(f"/api/projects/{project_id}/story/bible").json()
    assert bible["bible"]["synopsis"] == "林凡的成长故事"
    assert bible["bible"]["characters"][0]["name"] == "林凡"


def test_ai_writing_injects_bible_context(client, monkeypatch):
    project_id, novel_id = _create_novel_with_chapters(client, count=1)
    db_path = client.app.state.settings.db_path
    StoryRepository(db_path).save_bible(
        project_id,
        StoryBible(
            synopsis="林凡的成长故事",
            characters=[{"name": "林凡", "summary": "主角", "role_hint": "主角"}],
        ),
    )

    captured = {}

    def fake_chat(self, model_id, messages, temperature=0.8):
        captured["messages"] = messages
        return "续写正文"

    monkeypatch.setattr(ProviderManager, "chat", fake_chat)
    chapter = client.get(
        f"/api/projects/{project_id}/novels/{novel_id}"
    ).json()["chapters"][0]
    response = client.post(
        f"/api/projects/{project_id}/novels/{novel_id}/ai/continue",
        json={"model_id": "model_x", "chapter_id": chapter["id"]},
    )
    assert response.status_code == 200
    system = captured["messages"][0]["content"]
    assert "林凡" in system
    assert "Story Bible" in system
