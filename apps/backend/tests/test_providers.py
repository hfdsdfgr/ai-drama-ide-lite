"""Provider / Model 测试（Phase 3 — AI Provider 基础系统）。"""

from fastapi.testclient import TestClient

from app.core.config import Settings
from app.main import create_app
from app.services.secret_store import MemorySecretStore
from app.services.vendor_presets import classify_model


def _create_provider(client, **kwargs):
    payload = {"preset_key": "openai", "api_key": "sk-test-123", **kwargs}
    return client.post("/api/providers", json=payload)


def test_presets_listed(client):
    response = client.get("/api/providers/presets")
    assert response.status_code == 200
    presets = {p["key"]: p for p in response.json()}
    assert "openai" in presets and "ollama" in presets and "bailian" in presets
    assert "bailian-intl" in presets
    assert presets["openai"]["discoverable"] is True
    # 百炼国际站实测支持 OpenAI 兼容 /models（2026-08-13）
    assert presets["bailian"]["discoverable"] is True
    assert presets["bailian"]["base_url"] == "https://dashscope.aliyuncs.com/compatible-mode/v1"
    assert (
        presets["bailian-intl"]["base_url"]
        == "https://dashscope-intl.aliyuncs.com/compatible-mode/v1"
    )


def test_create_provider_with_preset(client):
    response = _create_provider(client)
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "OpenAI"
    assert body["api_base_url"] == "https://api.openai.com/v1"
    assert body["needs_key"] is True
    assert body["has_api_key"] is True
    assert body["preset_key"] == "openai"
    assert "sk-test-123" not in response.text


def test_duplicate_preset_provider_rejected(client):
    first = _create_provider(client)
    assert first.status_code == 201
    dup = _create_provider(client)
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "provider_already_exists"


def test_bailian_cn_and_intl_coexist(client):
    cn = client.post(
        "/api/providers", json={"preset_key": "bailian", "api_key": "sk-cn"}
    )
    intl = client.post(
        "/api/providers", json={"preset_key": "bailian-intl", "api_key": "sk-intl"}
    )
    assert cn.status_code == 201
    assert intl.status_code == 201
    assert cn.json()["api_base_url"].startswith("https://dashscope.aliyuncs.com")
    assert intl.json()["api_base_url"].startswith("https://dashscope-intl.aliyuncs.com")


class _FailingSecretStore:
    def set(self, username, value):
        raise RuntimeError("secret store boom")

    def get(self, username):
        return None

    def delete(self, username):
        return None


def test_provider_create_rolls_back_on_secret_failure(tmp_path):
    from app.core.config import Settings
    from app.main import create_app

    settings = Settings(data_dir=tmp_path, log_level="ERROR")
    client = TestClient(
        create_app(settings=settings, secret_store=_FailingSecretStore()),
        raise_server_exceptions=False,
    )
    response = client.post(
        "/api/providers", json={"preset_key": "openai", "api_key": "sk-x"}
    )
    assert response.status_code == 500
    # 密钥写入失败时不应留下 Provider 记录
    assert client.get("/api/providers").json() == []
    client.close()


def test_create_custom_provider_requires_base_url(client):
    response = client.post("/api/providers", json={"name": "自定义"})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "base_url_required"


def test_create_custom_provider(client):
    response = client.post(
        "/api/providers",
        json={
            "name": "我的API",
            "api_base_url": "https://example.com/v1",
            "needs_key": False,
        },
    )
    assert response.status_code == 201
    assert response.json()["has_api_key"] is False


def test_provider_without_key(client):
    response = client.post("/api/providers", json={"preset_key": "openai"})
    assert response.status_code == 201
    assert response.json()["has_api_key"] is False


def test_update_provider_key_overwrite(client):
    provider = _create_provider(client, api_key="sk-old").json()
    store = client.app.state.secret_store
    assert store.get(f"provider:{provider['id']}") == "sk-old"
    response = client.put(
        f"/api/providers/{provider['id']}", json={"api_key": "sk-new"}
    )
    assert response.status_code == 200
    assert store.get(f"provider:{provider['id']}") == "sk-new"


def test_provider_soft_delete_removes_secret(client):
    provider = _create_provider(client).json()
    store = client.app.state.secret_store
    assert client.delete(f"/api/providers/{provider['id']}").status_code == 204
    assert store.get(f"provider:{provider['id']}") is None
    assert client.get("/api/providers").json() == []


def test_secret_not_in_database_or_api(client, tmp_path):
    _create_provider(client, api_key="sk-super-secret-xyz")
    db_bytes = (tmp_path / "ai_drama_ide.db").read_bytes()
    assert b"sk-super-secret-xyz" not in db_bytes
    response = client.get("/api/providers")
    assert "sk-super-secret-xyz" not in response.text


def test_model_crud_and_duplicate(client):
    provider = _create_provider(client).json()
    pid = provider["id"]
    created = client.post(
        "/api/models",
        json={"provider_id": pid, "model_id": "gpt-4o", "model_type": "llm"},
    )
    assert created.status_code == 201
    body = created.json()
    assert body["model_id"] == "gpt-4o"
    assert body["provider_name"] == "OpenAI"

    dup = client.post(
        "/api/models",
        json={"provider_id": pid, "model_id": "gpt-4o", "model_type": "llm"},
    )
    assert dup.status_code == 409

    bad = client.post(
        "/api/models",
        json={"provider_id": pid, "model_id": "x", "model_type": "embedding"},
    )
    assert bad.status_code == 422

    audio = client.post(
        "/api/models",
        json={"provider_id": pid, "model_id": "glm-tts", "model_type": "audio"},
    )
    assert audio.status_code == 201
    assert "text_to_speech" in audio.json()["capabilities"]

    mid = body["id"]
    assert client.delete(f"/api/models/{mid}").status_code == 204
    assert client.get(f"/api/models/{mid}").status_code == 404


def test_default_uniqueness(client):
    provider = _create_provider(client).json()
    pid = provider["id"]
    m1 = client.post(
        "/api/models", json={"provider_id": pid, "model_id": "img-a", "model_type": "image"}
    ).json()
    m2 = client.post(
        "/api/models", json={"provider_id": pid, "model_id": "img-b", "model_type": "image"}
    ).json()
    client.post(f"/api/models/{m1['id']}/default", json={"model_type": "image"})
    client.post(f"/api/models/{m2['id']}/default", json={"model_type": "image"})
    models = client.get("/api/models", params={"provider_id": pid}).json()
    flags = {m["model_id"]: m["is_default_image"] for m in models}
    assert flags == {"img-a": False, "img-b": True}


def test_aggregation_filters(client):
    p1 = _create_provider(client).json()["id"]
    p2 = client.post(
        "/api/providers",
        json={"name": "本地", "api_base_url": "http://127.0.0.1:1/v1", "needs_key": False},
    ).json()["id"]
    client.post("/api/models", json={"provider_id": p1, "model_id": "gpt-4o", "model_type": "llm"})
    client.post("/api/models", json={"provider_id": p1, "model_id": "gpt-image-1", "model_type": "image"})
    client.post(
        "/api/models",
        json={"provider_id": p2, "model_id": "sdxl", "model_type": "image", "enabled": False},
    )
    response = client.get("/api/models", params={"model_type": "image", "enabled_only": True})
    assert response.status_code == 200
    ids = [m["model_id"] for m in response.json()]
    assert ids == ["gpt-image-1"]


def test_enabled_only_excludes_disabled_provider_and_keyless(client):
    # Provider 未配 Key（needs_key=True）→ 模型即使启用也不该出现在 enabled_only
    keyless = client.post(
        "/api/providers",
        json={
            "name": "无Key",
            "api_base_url": "http://127.0.0.1:1/v1",
            "needs_key": True,
        },
    ).json()
    client.post(
        "/api/models",
        json={
            "provider_id": keyless["id"],
            "model_id": "no-key-llm",
            "model_type": "llm",
        },
    )

    # Provider 被禁用 → 模型即使启用也不该出现在 enabled_only
    disabled = client.post(
        "/api/providers",
        json={
            "name": "被禁用",
            "api_base_url": "http://127.0.0.1:1/v1",
            "needs_key": False,
        },
    ).json()
    client.post(
        "/api/models",
        json={
            "provider_id": disabled["id"],
            "model_id": "disabled-provider-llm",
            "model_type": "llm",
        },
    )
    client.put(f"/api/providers/{disabled['id']}", json={"enabled": False})

    # 正常可用的对照
    ok = client.post(
        "/api/providers",
        json={
            "name": "可用",
            "api_base_url": "http://127.0.0.1:1/v1",
            "needs_key": False,
        },
    ).json()
    client.post(
        "/api/models",
        json={
            "provider_id": ok["id"],
            "model_id": "ok-llm",
            "model_type": "llm",
        },
    )

    response = client.get("/api/models", params={"model_type": "llm", "enabled_only": True})
    ids = [m["model_id"] for m in response.json()]
    assert "no-key-llm" not in ids
    assert "disabled-provider-llm" not in ids
    assert "ok-llm" in ids


def test_discover_models_classification(client, monkeypatch):
    provider = client.post(
        "/api/providers",
        json={"preset_key": "openai", "api_key": "sk-openai"},
    ).json()
    pid = provider["id"]

    import app.api.routes.providers as routes

    monkeypatch.setattr(
        routes,
        "fetch_model_ids",
        lambda base_url, api_key, protocol="openai_compat": [
            "gpt-4o",
            "gpt-image-1",
        ],
    )
    response = client.post(f"/api/providers/{pid}/discover-models")
    assert response.status_code == 200
    types = {m["model_id"]: m["model_type"] for m in response.json()}
    assert types["gpt-4o"] == "llm"
    assert types["gpt-image-1"] == "image"
    assert types["sora-2"] == "video"
    # 幂等：再次拉取不产生重复
    client.post(f"/api/providers/{pid}/discover-models")
    assert len(client.get("/api/models", params={"provider_id": pid}).json()) == len(types)


def test_discover_bailian_supported(client, monkeypatch):
    provider = client.post(
        "/api/providers",
        json={"preset_key": "bailian", "api_key": "sk-bailian"},
    ).json()

    import app.api.routes.providers as routes

    monkeypatch.setattr(
        routes,
        "fetch_model_ids",
        lambda base_url, api_key, protocol="openai_compat": [
            "qwen-plus",
            "qwen-image-plus",
            "wan2.1-t2v",
        ],
    )
    response = client.post(f"/api/providers/{provider['id']}/discover-models")
    assert response.status_code == 200
    types = {m["model_id"]: m["model_type"] for m in response.json()}
    assert types["qwen-plus"] == "llm"
    assert types["qwen-image-plus"] == "image"
    assert types["wan2.1-t2v"] == "video"
    assert types["wan2.2-i2v-plus"] == "video"


def test_preset_models_endpoint(client):
    response = client.get("/api/providers/presets/bailian/models")
    assert response.status_code == 200
    items = response.json()
    assert any(m["id"] == "qwen-plus" and m["type"] == "llm" for m in items)
    assert any(m["id"] == "wan2.1-t2v" and m["type"] == "video" for m in items)
    assert client.get("/api/providers/presets/unknown/models").status_code == 422


def test_preset_models_shared_between_bailian_sites(client):
    cn = client.get("/api/providers/presets/bailian/models").json()
    intl = client.get("/api/providers/presets/bailian-intl/models").json()
    assert {m["id"] for m in cn} == {m["id"] for m in intl}


def test_bulk_add_models_with_types(client):
    provider = client.post(
        "/api/providers",
        json={"preset_key": "bailian", "api_key": "sk-bailian"},
    ).json()
    response = client.post(
        f"/api/providers/{provider['id']}/models/bulk",
        json={"model_ids": ["qwen-plus", "wan2.1-t2v", "qwen-plus"]},
    )
    assert response.status_code == 201
    by_id = {m["model_id"]: m["model_type"] for m in response.json()}
    assert by_id == {"qwen-plus": "llm", "wan2.1-t2v": "video"}
    # 重复项跳过，总共只有 2 个模型
    remaining = client.get("/api/models", params={"provider_id": provider["id"]}).json()
    assert len(remaining) == 2


def test_discover_requires_key(client):
    provider = client.post("/api/providers", json={"preset_key": "openai"}).json()
    response = client.post(f"/api/providers/{provider['id']}/discover-models")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "api_key_required"


def test_persistence_across_restart(tmp_path):
    store = MemorySecretStore()
    settings = Settings(data_dir=tmp_path, log_level="ERROR")
    client1 = TestClient(create_app(settings=settings, secret_store=store))
    provider = _create_provider(client1).json()
    client1.post(
        "/api/models",
        json={"provider_id": provider["id"], "model_id": "gpt-4o"},
    )
    client1.close()

    client2 = TestClient(create_app(settings=settings, secret_store=store))
    providers = client2.get("/api/providers").json()
    assert providers[0]["id"] == provider["id"]
    assert providers[0]["has_api_key"] is True
    models = client2.get("/api/models", params={"provider_id": provider["id"]}).json()
    assert [m["model_id"] for m in models] == ["gpt-4o"]
    client2.close()


def test_classify_rules():
    assert classify_model("openai", "gpt-image-1") == "image"
    assert classify_model("openai", "gpt-4o") == "llm"
    assert classify_model("bailian", "wanx2.1-t2i") == "image"
    assert classify_model("bailian", "wan2.1-t2v") == "video"
    assert classify_model("bailian", "qwen-audio-3.0-asr-flash") == "audio"
    assert classify_model("bailian", "qwen-tts") == "audio"
    assert classify_model(None, "anything") == "llm"
