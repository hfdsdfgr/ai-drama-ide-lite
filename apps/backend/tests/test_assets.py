"""Phase 8 — Asset Engine 测试。"""

import json
import time

from app.db.database import get_connection
from app.schemas.story import StoryBible
from app.services.adapters.manager import ProviderManager
from app.services.asset_service import ASSET_IMAGE_SPECS, AssetGenerationService
from app.services.story_repo import StoryRepository


def _asset_bible_json() -> str:
    return json.dumps(
        {
            "synopsis": "林凡的成长故事",
            "characters": [
                {
                    "name": "林凡",
                    "aliases": ["林"],
                    "summary": "主角",
                    "role_hint": "主角",
                    "identity": "男主，18岁，青云镇少年",
                    "appearance": "剑眉星目，黑发",
                    "hairstyle": "黑色短发",
                    "costume": "青布长衫",
                    "build": "修长",
                    "marks": "",
                    "personality": "坚毅，隐忍",
                    "style": "国风动漫",
                    "reference_prompt": (
                        "male protagonist, 18 years old, short black hair, "
                        "dark eyes, green cloth robe, consistent character design"
                    ),
                }
            ],
            "locations": [
                {
                    "name": "青云镇",
                    "description": "小镇",
                    "environment": "群山环绕的江南小镇",
                    "time": "白天",
                    "lighting": "自然光",
                    "style": "国风动漫",
                    "reference_prompt": "a mountain town, sunny day, 16:9",
                }
            ],
            "props": [
                {
                    "name": "玉佩",
                    "description": "信物",
                    "material": "白玉",
                    "reference": "主角随身佩戴",
                    "reference_prompt": "a white jade pendant, close-up",
                }
            ],
            "events": [],
            "conflicts": [],
            "plotlines": [],
            "foreshadowing": [],
        },
        ensure_ascii=False,
    )


def _create_project_with_bible(client) -> str:
    project = client.post("/api/projects", json={"name": "资产项目"}).json()
    repo = StoryRepository(client.app.state.settings.db_path)
    repo.save_bible(
        project["id"],
        StoryBible.model_validate_json(_asset_bible_json()),
    )
    return project["id"]


def _wait_terminal(service, job_id, timeout=10):
    deadline = time.time() + timeout
    while time.time() < deadline:
        job = service.get(job_id)
        if job["status"] in ("completed", "failed", "cancelled"):
            return job
        time.sleep(0.05)
    raise AssertionError("job did not reach terminal state")


def test_save_bible_assigns_stable_asset_ids(client):
    project_id = _create_project_with_bible(client)
    db_path = client.app.state.settings.db_path
    repo = StoryRepository(db_path)

    with get_connection(db_path) as conn:
        rows = conn.execute(
            "SELECT id, asset_type, name, prompt FROM assets WHERE project_id = ? ORDER BY asset_type",
            (project_id,),
        ).fetchall()
    by_name = {r["name"]: r for r in rows}
    assert by_name["林凡"]["id"] == "character_林凡_001"
    assert by_name["青云镇"]["id"] == "location_青云镇_001"
    assert by_name["玉佩"]["id"] == "prop_玉佩_001"
    assert "consistent character design" in by_name["林凡"]["prompt"]

    # 再次保存（如增量合并）Asset ID 必须复用，不能漂移
    repo.save_bible(project_id, repo.get_bible(project_id))
    bible = repo.get_bible(project_id)
    assert bible.characters[0].asset_id == "character_林凡_001"
    with get_connection(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM assets WHERE project_id = ?", (project_id,)
        ).fetchone()["c"]
    assert count == 3


def test_asset_specs_are_fixed_format(client):
    project_id = _create_project_with_bible(client)
    response = client.get(f"/api/projects/{project_id}/assets/specs")
    assert response.status_code == 200
    specs = response.json()["specs"]
    assert specs["character"]["aspect_ratio"] == "2:3"
    assert specs["character"]["width"] == 1024
    assert specs["character"]["height"] == 1536
    assert specs["location"]["aspect_ratio"] == "16:9"
    assert specs["prop"]["aspect_ratio"] == "1:1"
    assert ASSET_IMAGE_SPECS == specs


def test_list_assets_includes_spec(client):
    project_id = _create_project_with_bible(client)
    response = client.get(f"/api/projects/{project_id}/assets")
    assert response.status_code == 200
    assets = response.json()
    assert len(assets) == 3
    character = next(a for a in assets if a["asset_type"] == "character")
    assert character["asset_id"] == "character_林凡_001"
    assert character["image_spec"]["aspect_ratio"] == "2:3"
    assert character["fields"]["costume"] == "青布长衫"
    assert character["reference_prompt"].startswith("male protagonist")


def test_update_asset_persists(client):
    project_id = _create_project_with_bible(client)
    response = client.put(
        f"/api/projects/{project_id}/assets",
        json={
            "asset_type": "character",
            "name": "林凡",
            "patch": {"costume": "黑色劲装", "marks": "左眼角泪痣"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["costume"] == "黑色劲装"
    assert body["fields"]["marks"] == "左眼角泪痣"
    assert body["asset_id"] == "character_林凡_001"

    repo = StoryRepository(client.app.state.settings.db_path)
    bible = repo.get_bible(project_id)
    assert bible.characters[0].costume == "黑色劲装"


def test_update_asset_rejects_name_and_asset_id(client):
    project_id = _create_project_with_bible(client)
    response = client.put(
        f"/api/projects/{project_id}/assets",
        json={
            "asset_type": "character",
            "name": "林凡",
            "patch": {"name": "改名", "asset_id": "hacked"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["fields"]["name"] == "林凡"
    assert body["asset_id"] == "character_林凡_001"


def test_delete_asset_removes_from_bible_and_tables(client):
    project_id = _create_project_with_bible(client)
    response = client.request(
        "DELETE",
        f"/api/projects/{project_id}/assets",
        json={"asset_type": "location", "name": "青云镇"},
    )
    assert response.status_code == 204

    repo = StoryRepository(client.app.state.settings.db_path)
    bible = repo.get_bible(project_id)
    assert len(bible.locations) == 0
    with get_connection(client.app.state.settings.db_path) as conn:
        row = conn.execute(
            "SELECT id FROM assets WHERE project_id = ? AND name = '青云镇'",
            (project_id,),
        ).fetchone()
        loc = conn.execute(
            "SELECT id FROM locations WHERE project_id = ? AND name = '青云镇'",
            (project_id,),
        ).fetchone()
    assert row is None
    assert loc is None

    # 重复删除 → 404
    again = client.request(
        "DELETE",
        f"/api/projects/{project_id}/assets",
        json={"asset_type": "location", "name": "青云镇"},
    )
    assert again.status_code == 404


def test_generate_fills_empty_fields_without_overwrite(client):
    project_id = _create_project_with_bible(client)
    db_path = client.app.state.settings.db_path

    class _FakeManager:
        def chat(self, model_id, messages, temperature=0.8):
            return json.dumps(
                {
                    "characters": [
                        {
                            "name": "林凡",
                            "identity": "被 AI 改写的身份",  # 已有值 → 不覆盖
                            "marks": "右肩龙纹身",  # 空值 → 填充
                            "reference_prompt": "new prompt",  # 已有值 → 不覆盖
                        }
                    ],
                    "locations": [],
                    "props": [],
                },
                ensure_ascii=False,
            )

    service = AssetGenerationService(_FakeManager(), db_path)
    job = service.start(project_id, model_id="model_x")
    finished = _wait_terminal(service, job["job_id"])
    assert finished["status"] == "completed"

    repo = StoryRepository(db_path)
    character = repo.get_bible(project_id).characters[0]
    assert character.identity == "男主，18岁，青云镇少年"  # 未被覆盖
    assert character.marks == "右肩龙纹身"  # 空字段被填充
    assert character.reference_prompt.startswith("male protagonist")  # 未被覆盖


def test_generate_requires_existing_assets(client):
    project = client.post("/api/projects", json={"name": "空项目"}).json()
    service = AssetGenerationService(
        client.app.state.provider_manager, client.app.state.settings.db_path
    )
    try:
        service.start(project["id"], model_id="model_x")
    except Exception as exc:
        assert getattr(exc, "code", "") == "no_assets"
    else:
        raise AssertionError("should raise no_assets")


def test_generate_endpoint_polls_to_completed(client, monkeypatch):
    project_id = _create_project_with_bible(client)

    def fake_chat(self, model_id, messages, temperature=0.8):
        return json.dumps(
            {
                "characters": [
                    {
                        "name": "林凡",
                        "marks": "右肩龙纹身",
                        "personality": "冷静",
                    }
                ],
                "locations": [],
                "props": [],
            },
            ensure_ascii=False,
        )

    monkeypatch.setattr(ProviderManager, "chat", fake_chat)
    response = client.post(
        f"/api/projects/{project_id}/assets/generate",
        json={"model_id": "model_x"},
    )
    assert response.status_code == 201
    job_id = response.json()["job_id"]

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        job = client.get(
            f"/api/projects/{project_id}/assets/generate/{job_id}"
        ).json()
        status = job["status"]
        if status in ("completed", "failed", "cancelled"):
            break
        time.sleep(0.05)
    assert status == "completed"

    character = client.get(f"/api/projects/{project_id}/assets").json()[0]
    assert character["fields"]["marks"] == "右肩龙纹身"
    assert character["fields"]["personality"] == "坚毅，隐忍"  # 已有值不被覆盖
