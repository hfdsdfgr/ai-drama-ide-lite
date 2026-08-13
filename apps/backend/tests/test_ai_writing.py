"""AI 写作接口测试（LLM 调用，单模型单次调用）。"""

from app.services.adapters.manager import ProviderManager


def _provider_with_model(client, model_type="llm", enabled=True, needs_key=False):
    provider = client.post(
        "/api/providers",
        json={
            "name": "测试文本",
            "api_base_url": "http://127.0.0.1:9999/v1",
            "needs_key": needs_key,
        },
    ).json()
    model = client.post(
        "/api/models",
        json={
            "provider_id": provider["id"],
            "model_id": "test-llm",
            "model_type": model_type,
            "enabled": enabled,
        },
    ).json()
    project = client.post("/api/projects", json={"name": "AI项目"}).json()
    novel = client.post(
        f"/api/projects/{project['id']}/novels", json={"title": "小说"}
    ).json()
    chapter = client.post(
        f"/api/projects/{project['id']}/novels/{novel['id']}/chapters",
        json={"title": "第一章"},
    ).json()
    return project["id"], novel["id"], chapter["id"], model["id"]


def test_ai_continue(client, monkeypatch):
    captured = {}

    def fake_chat(self, model_id, messages):
        captured["model"] = model_id
        captured["content"] = messages[1]["content"]
        return "续写的正文"

    monkeypatch.setattr(ProviderManager, "chat", fake_chat)
    pid, nid, cid, mid = _provider_with_model(client)
    response = client.post(
        f"/api/projects/{pid}/novels/{nid}/ai/continue",
        json={"model_id": mid, "chapter_id": cid},
    )
    assert response.status_code == 200
    assert response.json()["text"] == "续写的正文"
    assert captured["model"] == mid
    assert "第一章" in captured["content"]


def test_ai_requires_llm_model(client):
    pid, nid, cid, mid = _provider_with_model(client, model_type="image")
    response = client.post(
        f"/api/projects/{pid}/novels/{nid}/ai/rewrite",
        json={"model_id": mid, "chapter_id": cid},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "not_llm_model"


def test_ai_requires_enabled_model(client):
    pid, nid, cid, mid = _provider_with_model(client, enabled=False)
    response = client.post(
        f"/api/projects/{pid}/novels/{nid}/ai/continue",
        json={"model_id": mid, "chapter_id": cid},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "model_disabled"


def test_ai_requires_provider_key(client):
    pid, nid, cid, mid = _provider_with_model(client, needs_key=True)
    response = client.post(
        f"/api/projects/{pid}/novels/{nid}/ai/continue",
        json={"model_id": mid, "chapter_id": cid},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "api_key_required"
