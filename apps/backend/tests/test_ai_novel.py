"""AI 撰写向导接口测试（AI 整本小说）。"""

import json

import pytest

from app.core.errors import AppError
from app.schemas.story import AiNovelBrief
from app.services.adapters.manager import ProviderManager
from app.services.story_repo import StoryRepository
from app.schemas.story import StoryBible


def _outline_json(count=2):
    names = ["第一章", "第二章", "第三章", "第四章", "第五章"]
    chapters = [
        {"title": names[i], "summary": f"{names[i]}要点"} for i in range(count)
    ]
    return json.dumps({"title": "我的新书", "chapters": chapters}, ensure_ascii=False)


def _chapter_json():
    return json.dumps(
        {
            "title": "第一章",
            "content": "林凡走在青云镇的街道上。",
            "summary": "林凡出场",
        },
        ensure_ascii=False,
    )


def _capture_chat(responses):
    box = {"responses": list(responses), "messages": []}

    def fake_chat(self, model_id, messages, temperature=0.8, timeout=60):
        box["messages"].append(messages)
        if box["responses"]:
            return box["responses"].pop(0)
        return "{}"

    return box, fake_chat


def _create_project(client):
    return client.post("/api/projects", json={"name": "AI撰写项目"}).json()["id"]


def _brief(**overrides):
    payload = {
        "genre": "玄幻",
        "audience": "青少年",
        "ideas": "主角穿越到异世界，拥有成长型金手指。",
        "complexity": 5,
        "chapter_count": 2,
    }
    payload.update(overrides)
    return payload


def test_ai_outline_endpoint(client, monkeypatch):
    project_id = _create_project(client)
    box, fake = _capture_chat([_outline_json(2)])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    response = client.post(
        f"/api/projects/{project_id}/story/ai-outline",
        json={"model_id": "model_x", "brief": _brief()},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "我的新书"
    assert [c["title"] for c in body["chapters"]] == ["第一章", "第二章"]
    # 提示词包含题材/受众/复杂程度/初步想法
    user = box["messages"][0][1]["content"]
    assert "玄幻" in user
    assert "青少年" in user
    assert "5/10" in user
    assert "穿越到异世界" in user


def test_continue_stream_no_chapters(client):
    project_id = _create_project(client)
    novel_id = client.post(
        f"/api/projects/{project_id}/novels", json={"title": "续写测试"}
    ).json()["id"]
    service = client.app.state.ai_novel_service
    with pytest.raises(AppError) as exc:
        list(
            service.continue_chapter_stream(
                project_id, novel_id, "model_1", AiNovelBrief(**_brief()), "", 3
            )
        )
    assert exc.value.code == "ai_continue_no_chapters"


def test_continue_stream_with_chapters(client, monkeypatch):
    project_id = _create_project(client)
    novel_id = client.post(
        f"/api/projects/{project_id}/novels", json={"title": "续写测试"}
    ).json()["id"]
    client.post(
        f"/api/projects/{project_id}/novels/{novel_id}/chapters",
        json={"title": "第一章", "content": "林凡出场，踏上修行之路。"},
    )
    box = {"messages": []}

    def fake_stream(self, model_id, messages, temperature=0.9, timeout=300):
        box["messages"].append(messages)
        yield "第一段。"
        yield "第二段。"

    monkeypatch.setattr(ProviderManager, "chat_stream", fake_stream)
    service = client.app.state.ai_novel_service
    deltas = list(
        service.continue_chapter_stream(
            project_id,
            novel_id,
            "model_1",
            AiNovelBrief(**_brief()),
            "加快节奏",
            3,
        )
    )
    assert deltas == ["第一段。", "第二段。"]
    user = box["messages"][0][1]["content"]
    assert "林凡出场" in user
    assert "加快节奏" in user


def test_ai_outline_count_mismatch(client, monkeypatch):
    project_id = _create_project(client)
    _, fake = _capture_chat([_outline_json(1)])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    response = client.post(
        f"/api/projects/{project_id}/story/ai-outline",
        json={"model_id": "model_x", "brief": _brief(chapter_count=3)},
    )
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "ai_outline_count_mismatch"


def test_ai_chapter_endpoint(client, monkeypatch):
    project_id = _create_project(client)
    box, fake = _capture_chat([_chapter_json()])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    outline = [
        {"title": "第一章", "summary": "主角登场"},
        {"title": "第二章", "summary": "获得金手指"},
    ]
    response = client.post(
        f"/api/projects/{project_id}/story/ai-chapter",
        json={
            "model_id": "model_x",
            "brief": _brief(),
            "outline": outline,
            "chapter_index": 0,
            "user_instruction": "节奏快一点",
            "previous_summaries": [],
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["title"] == "第一章"
    assert "林凡走在青云镇" in body["content"]
    assert body["summary"] == "林凡出场"
    user = box["messages"][0][1]["content"]
    assert "1/2" in user
    assert "节奏快一点" in user


def test_ai_chapter_stream_endpoint(client, monkeypatch):
    project_id = _create_project(client)

    def fake_stream(self, model_id, messages, temperature=0.8, timeout=180):
        yield "这是"
        yield "流式"
        yield "正文"

    monkeypatch.setattr(ProviderManager, "chat_stream", fake_stream)
    response = client.post(
        f"/api/projects/{project_id}/story/ai-chapter-stream",
        json={
            "model_id": "model_x",
            "brief": _brief(),
            "outline": [{"title": "第一章", "summary": "主角登场"}],
            "chapter_index": 0,
        },
    )
    assert response.status_code == 200
    assert "这是" in response.text
    assert "流式" in response.text
    assert "done" in response.text


def test_ai_chapter_out_of_range(client, monkeypatch):
    project_id = _create_project(client)
    _, fake = _capture_chat([])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    response = client.post(
        f"/api/projects/{project_id}/story/ai-chapter",
        json={
            "model_id": "model_x",
            "brief": _brief(),
            "outline": [{"title": "第一章", "summary": "主角登场"}],
            "chapter_index": 5,
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "ai_chapter_out_of_range"


def test_ai_chapter_injects_bible_context(client, monkeypatch):
    project_id = _create_project(client)
    StoryRepository(client.app.state.settings.db_path).save_bible(
        project_id,
        StoryBible(
            synopsis="林凡的成长故事",
            characters=[{"name": "林凡", "summary": "主角", "role_hint": "主角"}],
        ),
    )
    box, fake = _capture_chat([_chapter_json()])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    response = client.post(
        f"/api/projects/{project_id}/story/ai-chapter",
        json={
            "model_id": "model_x",
            "brief": _brief(),
            "outline": [{"title": "第一章", "summary": "主角登场"}],
            "chapter_index": 0,
        },
    )
    assert response.status_code == 200
    user = box["messages"][0][1]["content"]
    assert "林凡" in user
    assert "已有故事设定" in user


def test_brief_complexity_and_count_validation(client):
    project_id = _create_project(client)
    response = client.post(
        f"/api/projects/{project_id}/story/ai-outline",
        json={"model_id": "model_x", "brief": _brief(complexity=11)},
    )
    assert response.status_code == 422
    response = client.post(
        f"/api/projects/{project_id}/story/ai-outline",
        json={"model_id": "model_x", "brief": _brief(chapter_count=0)},
    )
    assert response.status_code == 422
