"""剧本引擎接口测试（Phase 7 — Script Engine）。"""

import json

import pytest

from app.core.errors import AppError
from app.services.adapters.manager import ProviderManager


def _episode_json():
    return json.dumps(
        {
            "episode": {"title": "第一集 风起", "summary": "林凡登场，踏上修行之路。"},
            "scenes": [
                {
                    "title": "宗门大殿",
                    "slugline": "INT. 宗门大殿 - 夜",
                    "action": "林凡踏入大殿，四周弟子窃窃私语。",
                    "dialogue": "长老：你终于来了。\n林凡：我来赴约。",
                },
                {
                    "title": "山门",
                    "slugline": "EXT. 山门 - 日",
                    "action": "林凡与天骄对峙，剑光交错。",
                    "dialogue": "天骄：今日你走不出这道门。",
                },
            ],
        },
        ensure_ascii=False,
    )


def _shots_json():
    return json.dumps(
        {
            "shots": [
                {
                    "shot_type": "wide",
                    "camera": "固定机位，全景",
                    "characters": "林凡, 长老",
                    "action": "林凡踏入大殿。",
                    "lighting": "烛光明暗交错",
                    "dialogue": "",
                    "duration": 4,
                    "prompt": "全景：少年踏入昏暗大殿，烛火摇曳。",
                },
                {
                    "shot_type": "close-up",
                    "camera": "缓慢推近",
                    "characters": "林凡",
                    "action": "林凡抬头，眼神坚定。",
                    "lighting": "面部被烛光照亮",
                    "dialogue": "林凡：我来赴约。",
                    "duration": 3,
                    "prompt": "特写：少年坚定的眼神，烛光映面。",
                },
            ]
        },
        ensure_ascii=False,
    )


def _capture_chat(responses):
    box = {"responses": list(responses), "messages": []}

    def fake_chat(self, model_id, messages, temperature=0.8, timeout=300):
        box["messages"].append(messages)
        if box["responses"]:
            return box["responses"].pop(0)
        return "{}"

    return box, fake_chat


def _create_project_with_novel(client):
    project_id = client.post("/api/projects", json={"name": "剧本项目"}).json()["id"]
    novel_id = client.post(
        f"/api/projects/{project_id}/novels", json={"title": "逆袭"}
    ).json()["id"]
    client.post(
        f"/api/projects/{project_id}/novels/{novel_id}/chapters",
        json={"title": "第一章", "content": "林凡踏入宗门大殿，与长老对峙。"},
    )
    return project_id, novel_id


def test_generate_episode_script(client, monkeypatch):
    project_id, novel_id = _create_project_with_novel(client)
    box, fake = _capture_chat([_episode_json()])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    response = client.post(
        f"/api/projects/{project_id}/script/generate-episode",
        json={"novel_id": novel_id, "model_id": "model_x", "chapter_index": 0},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["episode"]["title"] == "第一集 风起"
    assert len(body["scenes"]) == 2
    assert body["scenes"][0]["slugline"].startswith("INT.")
    user = box["messages"][0][1]["content"]
    assert "宗门大殿" in user


def test_generate_episode_no_chapters(client):
    project_id = client.post("/api/projects", json={"name": "空小说"}).json()["id"]
    novel_id = client.post(
        f"/api/projects/{project_id}/novels", json={"title": "空"}
    ).json()["id"]
    service = client.app.state.ai_script_service
    with pytest.raises(AppError) as exc:
        service.generate_episode_script(
            project_id, novel_id, "model_x", 0, ""
        )
    assert exc.value.code == "script_no_chapters"


def test_save_episode_script_and_detail(client):
    project_id, novel_id = _create_project_with_novel(client)
    payload = {
        "novel_id": novel_id,
        "chapter_index": 0,
        "episode": {"title": "第一集", "summary": "林凡登场"},
        "scenes": [
            {
                "title": "大殿",
                "slugline": "INT. 大殿 - 夜",
                "action": "对峙",
                "dialogue": "长老：来吧。",
            }
        ],
    }
    response = client.post(
        f"/api/projects/{project_id}/script/save-episode-script", json=payload
    )
    assert response.status_code == 201
    episode_id = response.json()["episode"]["id"]
    detail = client.get(
        f"/api/projects/{project_id}/script/episodes/{episode_id}"
    ).json()
    assert detail["episode"]["title"] == "第一集"
    assert len(detail["scenes"]) == 1
    assert detail["scenes"][0]["slugline"] == "INT. 大殿 - 夜"


def test_generate_shots(client, monkeypatch):
    project_id, novel_id = _create_project_with_novel(client)
    saved = client.post(
        f"/api/projects/{project_id}/script/save-episode-script",
        json={
            "novel_id": novel_id,
            "chapter_index": 0,
            "episode": {"title": "第一集", "summary": "s"},
            "scenes": [
                {
                    "title": "大殿",
                    "slugline": "INT. 大殿 - 夜",
                    "action": "对峙",
                    "dialogue": "长老：来吧。",
                }
            ],
        },
    ).json()
    scene_id = saved["scenes"][0]["id"]
    box, fake = _capture_chat([_shots_json()])
    monkeypatch.setattr(ProviderManager, "chat", fake)
    response = client.post(
        f"/api/projects/{project_id}/script/scenes/{scene_id}/generate-shots",
        json={"model_id": "model_x", "scene_id": scene_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert len(body["shots"]) == 2
    assert body["shots"][0]["shot_type"] == "wide"
    assert body["shots"][0]["duration"] == 4


def test_save_scene_shots(client):
    project_id, novel_id = _create_project_with_novel(client)
    saved = client.post(
        f"/api/projects/{project_id}/script/save-episode-script",
        json={
            "novel_id": novel_id,
            "chapter_index": 0,
            "episode": {"title": "第一集", "summary": "s"},
            "scenes": [
                {
                    "title": "大殿",
                    "slugline": "INT. 大殿 - 夜",
                    "action": "对峙",
                    "dialogue": "长老：来吧。",
                }
            ],
        },
    ).json()
    scene_id = saved["scenes"][0]["id"]
    response = client.post(
        f"/api/projects/{project_id}/script/scenes/{scene_id}/save-shots",
        json={
            "shots": [
                {
                    "shot_type": "close-up",
                    "camera": "推近",
                    "characters": "林凡",
                    "action": "抬头",
                    "lighting": "烛光",
                    "dialogue": "林凡：我来。",
                    "duration": 3,
                    "prompt": "特写：少年眼神。",
                }
            ]
        },
    )
    assert response.status_code == 201
    assert response.json()["shots"][0]["shot_number"] == 1
